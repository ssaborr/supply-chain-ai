import asyncio
import smtplib
import logging
from email.message import EmailMessage
from app.core.config import settings

logger = logging.getLogger("email_service")

def _sync_send_email(to_email: str, subject: str, body_text: str) -> dict:
    """Synchronous function to perform the SMTP network request."""
    msg = EmailMessage()
    msg.set_content(body_text)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    
    logger.info(f"Attempting to send email via SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} to {to_email}...")
    
    # dispatch using real SMTP server if configured
    try:

        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0)
            # switch to TLS encryption to keep data secure
            try:
                server.starttls()
            except Exception as tls_err:
                logger.debug(f"TLS start failed or not supported: {tls_err}")

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
        server.send_message(msg)
        server.quit()
        logger.info(f"Email successfully sent to {to_email}.")
        return {"success": True, "simulated": False}
        
    except Exception as e:
        logger.warning(
            f"SMTP send failed: {e}. Simulating email delivery for debugging. "
            f"Please run a local debugging server e.g. 'python -m smtpd -c DebuggingServer -n localhost:1025' to test SMTP."
        )
        # fallback: print details to console for debugging
        logger.info(
            f"\n--- SIMULATED SENT EMAIL ---\n"
            f"From: {settings.SMTP_FROM}\n"
            f"To: {to_email}\n"
            f"Subject: {subject}\n"
            f"Body:\n{body_text}\n"
            f"-----------------------------\n"
        )
        return {"success": True, "simulated": True, "error": str(e)}

async def send_email_notification(to_email: str, subject: str, body_text: str) -> dict:
    """Async wrapper that schedules the synchronous SMTP operation in a worker thread."""
    return await asyncio.to_thread(_sync_send_email, to_email, subject, body_text)
