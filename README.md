# Extensões privadas para Mihon

Fontes experimentais compatíveis com a infraestrutura Keiyoushi. Repositório privado; não associado ao Mihon ou BlitzToons.

## BlitzToons

Módulo inicial em `src/pt/blitztoons`. Inclui catálogo, pesquisa experimental, detalhes, capítulos e imagens publicamente acessíveis. Não implementa login, bypass de VIP ou contorno de controles de acesso. Testes reais no Mihon ainda pendentes.

## APK via GitHub Actions

O workflow `.github/workflows/build-apk.yml` importa os módulos para uma cópia temporária do framework Keiyoushi, executa `assembleDebug` e oferece os APKs como artifacts privados por sete dias. Nenhuma release pública será criada.

Acesse a aba Actions, abra o workflow "Compilar extensões Mihon" e baixe "mihon-extensoes-apk-debug" de uma execução bem-sucedida. Os builds usam runners hospedados pelo GitHub; o código não é publicado em repositórios externos.

Para adicionar fontes, crie módulos em `src/<idioma>/<nome>`. APKs debug podem ter assinaturas diferentes entre execuções.
