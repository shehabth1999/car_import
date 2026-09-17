# -*- coding: utf-8 -*-
"""The customer's tracking token — one per deal, secret, never a guessable id."""
import secrets


def new_token():
    return secrets.token_hex(16)


def ensure_token(deal):
    """The deal's token, minting one if it has none. Written without hooks: a
    token is bookkeeping, not a stage move."""
    if deal.public_token:
        return deal.public_token
    token = new_token()
    type(deal)._base_manager.filter(pk=deal.pk).update(public_token=token)
    deal.public_token = token
    return token
