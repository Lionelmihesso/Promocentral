"""Envoi du lien magique par SMTP, contre un faux serveur local (protocole minimal, sans TLS)."""
import email
import email.policy
import socket
import threading
import unittest

from radar.accounts import MailError, SmtpOutbox


class FakeSMTP:
    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.messages, self.auth = [], []
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        conn, _ = self.sock.accept()
        f = conn.makefile("rb")
        send = lambda line: conn.sendall((line + "\r\n").encode())
        send("220 fake")
        data, in_data = [], False
        for raw in f:
            line = raw.decode().rstrip("\r\n")
            if in_data:
                if line == ".":
                    self.messages.append("\r\n".join(data)); data, in_data = [], False; send("250 ok")
                else:
                    data.append(line[1:] if line.startswith("..") else line)
                continue
            cmd = line.split(" ", 1)[0].upper()
            if cmd == "EHLO":
                conn.sendall(b"250-fake\r\n250 AUTH PLAIN\r\n")
            elif cmd == "AUTH":
                self.auth.append(line); send("235 ok")
            elif cmd == "DATA":
                in_data = True; send("354 go")
            elif cmd == "QUIT":
                send("221 bye"); break
            else:
                send("250 ok")
        conn.close()


class SmtpSend(unittest.TestCase):
    def test_link_is_sent_by_smtp(self):
        srv = FakeSMTP()
        box = SmtpOutbox({"DEALS_SMTP_HOST": "127.0.0.1", "DEALS_SMTP_PORT": str(srv.port), "DEALS_SMTP_TLS": "none",
                          "DEALS_SMTP_USER": "u", "DEALS_SMTP_PASSWORD": "p", "DEALS_MAIL_FROM": "Deals <bonjour@deals.test>"})
        link = "https://deals.test/api/r/auth/verify?token=abc123"
        box.send("lea@exemple.fr", link)
        self.assertEqual(len(srv.messages), 1)
        msg = email.message_from_string(srv.messages[0], policy=email.policy.default)
        self.assertEqual(msg["To"], "lea@exemple.fr")
        self.assertEqual(msg["Subject"], "Votre lien de connexion Deals")
        self.assertIn(link, msg.get_body(("plain",)).get_content())
        self.assertIn(link, msg.get_body(("html",)).get_content())
        self.assertTrue(srv.auth)                                   # identifiants transmis

    def test_unreachable_server_gives_clear_error(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()   # port fermé
        box = SmtpOutbox({"DEALS_SMTP_HOST": "127.0.0.1", "DEALS_SMTP_PORT": str(port), "DEALS_SMTP_TLS": "none"})
        with self.assertRaises(MailError) as cm:
            box.send("lea@exemple.fr", "https://x/verify?token=t")
        self.assertEqual(cm.exception.status, 503)
        self.assertEqual(box.sent, [])


if __name__ == "__main__":
    unittest.main()
