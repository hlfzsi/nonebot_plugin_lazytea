import ujson
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError
import time


def default(v):
    try:
        if isinstance(v, set):
            return list(v)
        else:
            return str(v)
    except:
        return "不受支持的类型,请手动修改"


class MessageHeader(BaseModel):
    """消息头部结构
    Example:
        >>> header = MessageHeader(
        ...     msg_id="a1b2c3d4",
        ...     msg_type="request",
        ...     correlation_id="b2c3d4e5",
        ...     timestamp=time.time()
        ... )
    """
    msg_id: str
    msg_type: str  # Enum: request/response/broadcast/command
    correlation_id: Optional[str] = None
    timestamp: float = time.time()


class ProtocolMessage:
    """WebSocket 协议消息处理器"""
    VERSION = "1.0"
    SEPARATOR = "\x1e"  # ASCII Record Separator

    @classmethod
    def encode(cls, header: MessageHeader, payload: Any) -> str:
        """编码结构化消息
        Example:
            >>> header = MessageHeader(msg_id="123", msg_type="request", timestamp=time.time())
            >>> ProtocolMessage.encode(header, {"method": "ping"})
        """
        message = {
            "version": cls.VERSION,
            "header": header.model_dump(),
            "payload": payload
        }
        return ujson.dumps(message, default=default) + cls.SEPARATOR

    @classmethod
    def decode(cls, raw_data: str) -> Tuple[Optional[MessageHeader], Any]:
        """解码结构化消息
        Example:
            >>> raw = '{"version":"1.0","header":{"msg_id":"123","msg_type":"request",...}}\x1e'
            >>> ProtocolMessage.decode(raw)
        """
        try:
            data = ujson.loads(raw_data.strip(cls.SEPARATOR))
            header = MessageHeader(**data["header"])
            return header, data.get("payload")
        except (ujson.JSONDecodeError, KeyError, ValidationError) as e:
            return None, None


class RequestPayload(BaseModel):
    """请求负载结构
    Example:
        >>> payload = RequestPayload(method="get_user", params={"user_id": 123})
    """
    method: str
    params: Dict[str, Any]


class ResponsePayload(BaseModel):
    """响应负载结构,time字段不应当传入
    Example:
        >>> success_resp = ResponsePayload(code=200, data={"name": "Alice"})
        >>> error_resp = ResponsePayload(code=404, error="User not found")
    """
    code: int
    time: int = int(time.time()*1000)
    data: Any = Field(default_factory=dict)  # Usually A Dict
    error: Optional[str] = None


class HeartbeatPayload(BaseModel):
    """心跳负载结构
    Example:
        >>> hb_payload = HeartbeatPayload(status="alive")
    """
    status: str
