"""Fase 12: o app da mesa — as cinco telas servidas ao vivo do livro (D-35).

O app não tem lógica de negócio própria: cada tela é uma LENTE sobre o livro,
chamando os motores que os gates das fases 1–11 já provaram. E é estruturalmente
incapaz de escrever: a sessão Postgres abre com default_transaction_read_only=on.
"""
