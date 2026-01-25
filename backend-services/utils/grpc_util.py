"""
gRPC Utility Functions

Provides:
- gRPC-Web frame encoding/decoding
- gRPC Reflection service discovery
- Streaming frame handling
"""

import logging
import struct
from typing import AsyncGenerator

import httpx

logger = logging.getLogger('doorman.gateway')

# gRPC-Web flags
GRPC_WEB_FLAGS_NONE = 0x00
GRPC_WEB_FLAGS_TRAILERS = 0x80

# Frame format: 1 byte flag + 4 bytes length (big endian)
FRAME_HEADER_STRUCT = struct.Struct('>BI')


def encode_grpc_web_frame(data: bytes, flags: int = GRPC_WEB_FLAGS_NONE) -> bytes:
    """
    Encode data into a gRPC-Web frame.
    
    Args:
        data: Payload bytes
        flags: Frame flags (0x00 for data, 0x80 for trailers)
        
    Returns:
        Encoded frame bytes
    """
    header = FRAME_HEADER_STRUCT.pack(flags, len(data))
    return header + data


def decode_grpc_web_frame(frame: bytes) -> tuple[int, bytes, int]:
    """
    Decode a single gRPC-Web frame header.
    
    Args:
        frame: Frame bytes (must be at least 5 bytes)
        
    Returns:
        Tuple of (flags, payload_length, bytes_consumed)
    """
    if len(frame) < 5:
        return 0, 0, 0
    
    try:
        flags, length = FRAME_HEADER_STRUCT.unpack(frame[:5])
        return flags, length, 5
    except struct.error:
        return 0, 0, 0


async def parse_grpc_web_stream(stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[tuple[int, bytes], None]:
    """
    Parse a stream of gRPC-Web bytes into frames.
    
    Args:
        stream: Async generator yielding bytes
        
    Yields:
        Tuple of (flags, payload) for each complete frame
    """
    buffer = bytearray()
    
    async for chunk in stream:
        buffer.extend(chunk)
        
        while len(buffer) >= 5:
            flags, length, consumed = decode_grpc_web_frame(buffer)
            
            if len(buffer) < consumed + length:
                # Incomplete frame, wait for more data
                break
            
            # Extract payload
            payload = bytes(buffer[consumed:consumed + length])
            yield flags, payload
            
            # Remove processed frame
            del buffer[:consumed + length]


def create_grpc_web_response(payload: bytes, trailers: dict | None = None) -> bytes:
    """
    Create a complete gRPC-Web response body.
    
    Args:
        payload: Protobuf message bytes
        trailers: Optional trailers dictionary
        
    Returns:
        Complete response body bytes
    """
    response = bytearray()
    
    # Data frame
    response.extend(encode_grpc_web_frame(payload, GRPC_WEB_FLAGS_NONE))
    
    # Trailer frame
    trailer_lines = []
    trailer_lines.append('grpc-status:0')
    trailer_lines.append('grpc-message:OK')
    if trailers:
        for k, v in trailers.items():
            trailer_lines.append(f'{k}:{v}')
    
    trailer_bytes = '\r\n'.join(trailer_lines).encode('utf-8')
    response.extend(encode_grpc_web_frame(trailer_bytes, GRPC_WEB_FLAGS_TRAILERS))
    
    return bytes(response)


async def fetch_reflection_services(url: str, timeout: float = 10.0) -> list[str]:
    """
    Discover available gRPC services via Server Reflection.
    
    Note: This is a simplified implementation that uses the HTTP/2 proxy
    approach or assumes the server supports HTTP/1.1 gRPC (like Envoy).
    In a real gRPC client, we'd use grpcio reflection client.
    
    Args:
        url: gRPC endpoint URL
        timeout: Request timeout
        
    Returns:
        List of service names
    """
    # This placeholder returns empty list - implementing full gRPC reflection
    # client without grpcio-reflection dependency is complex.
    # In production, we'd use the `grpc_reflection` library.
    return []
