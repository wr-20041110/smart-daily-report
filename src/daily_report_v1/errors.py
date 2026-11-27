"""统一异常体系（design.md 模块职责：共享-异常）。"""


class DailyReportError(Exception):
    """所有业务异常的基类。"""


class ConfigError(DailyReportError):
    """配置加载或校验失败（成员重名、config.json 缺失/格式错误等）。"""


class CollectorError(DailyReportError):
    """采集层失败（网络错误、重试耗尽、请求超限等）。"""


class CredentialsMissingError(CollectorError):
    """采集或推送所需凭证缺失。编排层据此决定回退 mock。"""


class GeneratorError(DailyReportError):
    """生成层失败。"""


class StorageError(DailyReportError):
    """存储层失败。"""


class PushError(DailyReportError):
    """推送层失败。"""
