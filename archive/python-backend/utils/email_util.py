"""
Email Utility

Simple mock email service for sending notifications.
In production this would integrate with SES/SendGrid/SMTP.
"""

import logging
from typing import Any

logger = logging.getLogger('doorman.gateway')


async def send_email(to_email: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> bool:
    """
    Send an email notification (Mock).
    
    Args:
        to_email: Recipient email
        subject: Email subject
        body: Email body text
        metadata: Optional extra data for logging
        
    Returns:
        True if sent successfully
    """
    try:
        # In a real app we'd use boto3 SES or smtplib
        logger.info(f'📧 [MOCK EMAIL] To: {to_email} | Subject: {subject}')
        logger.info(f'--- Body ---\n{body}\n------------')
        
        if metadata:
            logger.info(f'Email Metadata: {metadata}')
            
        return True
    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        return False
