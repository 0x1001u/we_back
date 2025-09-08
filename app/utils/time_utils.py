from datetime import datetime, timedelta
from typing import Tuple, List


def get_time_range(date_str: str, start_hour: int, duration: int) -> Tuple[int, int]:
    """
    根据日期、开始小时和持续时间计算时间戳范围
    
    Args:
        date_str: 日期字符串 (YYYY-MM-DD)
        start_hour: 开始小时 (0-23)
        duration: 持续时间（小时）
        
    Returns:
        Tuple[int, int]: 开始时间戳和结束时间戳
    """
    # 解析日期
    date = datetime.strptime(date_str, '%Y-%m-%d')
    
    # 计算开始时间
    start_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    
    # 计算结束时间
    end_time = start_time + timedelta(hours=duration)
    
    # 转换为时间戳
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    
    return start_timestamp, end_timestamp


def get_date_range(start_date: str, days: int) -> List[str]:
    """
    获取日期范围列表
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        days: 天数
        
    Returns:
        List[str]: 日期列表
    """
    dates = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    
    for i in range(days):
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(date_str)
        current_date += timedelta(days=1)
    
    return dates


def timestamp_to_datetime(timestamp: int) -> datetime:
    """
    将时间戳转换为datetime对象
    
    Args:
        timestamp: 时间戳
        
    Returns:
        datetime: datetime对象
    """
    return datetime.fromtimestamp(timestamp)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    将datetime对象转换为时间戳
    
    Args:
        dt: datetime对象
        
    Returns:
        int: 时间戳
    """
    return int(dt.timestamp())