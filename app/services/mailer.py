"""Envio de e-mails (usado no "Esqueci minha senha").

Se o servidor de e-mail (SMTP) estiver configurado no .env, o e-mail é
enviado de verdade. Em desenvolvimento, sem SMTP, o link é mostrado no
terminal para você conseguir testar. Em produção sem SMTP, o envio falha
com um erro claro (nada é simulado).
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


class MailNotConfigured(RuntimeError):
    """O servidor de e-mail não foi configurado."""


def send_email(to: str, subject: str, body: str) -> None:
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        if current_app.debug or current_app.testing:
            # Desenvolvimento: mostra o e-mail no terminal.
            current_app.logger.warning("E-MAIL (modo desenvolvimento) para %s\n%s\n%s",
                                       to, subject, body)
            return
        raise MailNotConfigured("Configure MAIL_SERVER no .env para enviar e-mails.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("MAIL_FROM") or cfg.get("MAIL_USERNAME")
    msg["To"] = to
    msg.set_content(body)

    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as smtp:
        smtp.starttls()
        if cfg.get("MAIL_USERNAME"):
            smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)
