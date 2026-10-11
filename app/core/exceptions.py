class BusinessError(Exception):
    """业务异常：由全局异常处理器转换为 {code, msg, data} 统一响应"""

    def __init__(self, msg: str, status_code: int = 400):
        super().__init__(msg)
        self.msg = msg
        self.status_code = status_code


def ok(data=None, msg: str = "success") -> dict:
    return {"code": 0, "msg": msg, "data": data}
