# Deployment additions

This fork keeps the original BiliNote MIT license and copyright notice.
See `LICENSE` and `NOTICE.md`.

## Accounts and quotas

| Account role | Generation quota |
| --- | --- |
| Guest | 5 notes total per public IP |
| Free user | 5 notes per day |
| Privileged user | 50 notes per day |
| Administrator | Unlimited |

Daily quotas reset using the `Asia/Shanghai` timezone. Enforcement happens in
the backend before a generation task is accepted.

Registration requires a username, password, email address, and a five-character
graphical CAPTCHA. A phone number can be supplied optionally. SMS or email
verification requires a separate delivery provider and is not enabled by
default.

## Administrator access

Only administrators may modify providers, models, downloader cookies,
transcriber settings, proxy settings, or model downloads. The web application
also hides the global settings entry for non-administrators.

An operator can manage the first administrator from inside the backend
container:

```bash
python scripts/account_admin.py list
python scripts/account_admin.py set-role USERNAME admin
```

After that, administrators can manage roles from **Settings → Users and
permissions**.

## Browser extension

The production package is available from the deployed site at:

```text
/downloads/BiliNote-extension.zip
```

The package includes both the BiliNote MIT notice and the Vitesse WebExt MIT
notice.
