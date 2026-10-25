# Loja privada Mihon — instalação

O repositório GitHub permanece **privado**. A loja não pode ser adicionada diretamente por uma URL `raw.githubusercontent.com` de repositório privado porque o Mihon não envia um token de autenticação do GitHub.

A pasta `private-store` gerada pelo GitHub Actions contém:
- `index.pb` (catálogo v2 Protobuf GZIP)
- `repo.json` (metadados e assinatura do repositório)
- `index.json` e `index.min.json` (metadados auxiliares)
- `apk/` (arquivos APK)
- `icon/` (ícones)

## 1. Escolher um servidor acessível somente pela sua rede Tailscale

Em um Linux com Tailscale ativo, descubra a URL HTTPS privada com:

```bash
tailscale status
tailscale serve status
```

Seu domínio terá o formato `https://NOME-DO-DISPOSITIVO.NOME-DA-TAILNET.ts.net`. Esse endereço é **um exemplo de formato**, não uma URL gerada automaticamente por este projeto.

O computador que servir a loja deve permanecer ligado, e o Android com Mihon precisa ter Tailscale conectado à mesma tailnet.

## 2. Gerar o pacote com as URLs HTTPS corretas

No repositório GitHub: Settings → Secrets and variables → Actions → Variables → New repository variable.

- Nome: `PRIVATE_MIHON_BASE_URL`
- Valor: URL HTTPS privada do seu dispositivo Tailscale, **sem barra final**.

Depois execute o workflow em Actions → Compilar extensões Mihon → Run workflow. Baixe o artifact privado `mihon-loja-privada` e extraia para uma pasta do servidor, por exemplo `/srv/mihon-store`. A geração do pacote valida a assinatura dos APKs e constrói os arquivos de índice.

## 3. Ativar o servidor HTTPS privado

No dispositivo Linux com a pasta extraída:

```bash
sudo tailscale serve --bg --https=443 /srv/mihon-store
tailscale serve status
```

Se o comando pedir autorização para certificados HTTPS, habilite-os no painel do Tailscale.

**Use Serve, não Funnel.** Funnel expõe o servidor à internet pública, violando o requisito de privacidade.

## 4. Adicionar ao Mihon

No navegador Android, com o Tailscale conectado, teste:

```text
https://SEU-DISPOSITIVO.SUA-TAILNET.ts.net/repo.json
https://SEU-DISPOSITIVO.SUA-TAILNET.ts.net/index.pb
```

No Mihon, abra Mais → Configurações → Navegar → Repositórios de extensões e adicione a **URL real** até `/index.pb`. Confirme a chave de assinatura apresentada antes de confiar na loja.

O APK e o índice devem estar no mesmo servidor privado, e as URLs `apkUrl` e `iconUrl` precisam ser acessíveis ao Android. O nome do host do exemplo não deve ser usado literalmente.

## Cuidados

- Não copie os índices/APKs para GitHub Pages, jsDelivr ou um repositório público.
- Não compartilhe a URL e restrinja quem integra sua tailnet.
- Um build APK debug do GitHub Actions pode gerar uma **assinatura diferente** em cada execução. Se isso ocorrer, atualizações instaladas serão rejeitadas. Para atualizações automáticas estáveis, configure uma chave de assinatura persistente, mantida em GitHub Actions Secrets, antes de utilizar a loja em produção.
- O protótipo BlitzToons não foi validado por teste de uso no Mihon.
