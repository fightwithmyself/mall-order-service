import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.order import router as order_router
from app.api.product import router as product_router
from app.core.config import settings
from app.core.exceptions import BusinessError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="mall-order-service 电商订单服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "msg": exc.msg, "data": None})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    detail = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()[:3]]
    return JSONResponse(status_code=422, content={"code": 422, "msg": "请求参数错误", "data": detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.getLogger("app").exception("未处理异常 %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"code": 500, "msg": "服务器内部错误", "data": None})


app.include_router(product_router)
app.include_router(order_router)


@app.get("/api/health", tags=["系统"])
def health():
    return {"code": 0, "msg": "ok", "data": None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
