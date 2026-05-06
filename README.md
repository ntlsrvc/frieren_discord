# Frieren chapter check
 
GitHub Action que verifica se saiu capítulo novo de Frieren e avisa no Discord.
 
## O que faz
 
- Consulta o RSS da série no WeebCentral
- Envia um embed no Discord com o link quando há capítulo novo
- Envia um status informando há quantos dias o último capítulo foi lançado quando não há atualização
- Inclui um GIF do Giphy na mensagem

## Variáveis de ambiente
 
| Variável | Descrição |
|---|---|
| `DISCORD_WEBHOOK_URL` | Webhook do canal de notificações |
| `GIPHY_API_KEY` | Chave da API do Giphy |
