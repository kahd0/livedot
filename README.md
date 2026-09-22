# LiveDot

[![Versão mais recente](https://img.shields.io/github/v/release/kahd0/livedot?label=vers%C3%A3o)](https://github.com/kahd0/livedot/releases/latest)
[![Build do Windows](https://github.com/kahd0/livedot/actions/workflows/build-windows.yml/badge.svg)](https://github.com/kahd0/livedot/actions/workflows/build-windows.yml)
![Plataformas: Windows e Linux](https://img.shields.io/badge/plataformas-Windows%20%7C%20Linux%20(X11)-5865F2)
[![Licença MIT](https://img.shields.io/github/license/kahd0/livedot?label=licen%C3%A7a)](LICENSE)

Um ponto discreto no canto da tela que mostra se o seu microfone do Discord está aberto. Clique nele, ou use um atalho, para mutar e desmutar sem precisar abrir o Discord.

<p>
  <img src="manual/estado_fechado.png" width="64" alt="Ponto cinza: microfone fechado">
  <img src="manual/estado_aberto.png" width="64" alt="Ponto vermelho: microfone aberto">
  <img src="manual/estado_mensagem_direta.png" width="64" alt="Ponto com bolinha azul: mensagem nova">
</p>

Feito para quem passa o dia em chamada: bateu o olho, você sabe se estão te ouvindo.

## O que ele faz

- **Mostra o estado real do microfone.** Mutou pelo próprio Discord ou por um atalho dele? O ponto acompanha.
- **Muta com um clique ou com um atalho global**, que pode ser um botão lateral do mouse. Segurando o atalho, você fala só enquanto segura.
- **Avisa quando chega mensagem para você**, sem mostrar o texto na tela.
- **Protege o microfone:** entra nas chamadas já mutado e muta sozinho se você esquecer o microfone aberto sem falar.
- **Fica fora do caminho:** não tem janela nem ícone na barra de tarefas, e quase some quando você não está em chamada.
- Funciona no **Windows** e no **Linux** (X11).

## Sumário

- [Instalação](#instalação)
- [Primeira configuração](#primeira-configuração)
- [Como usar](#como-usar)
- [Personalizando](#personalizando)
- [Problemas comuns](#problemas-comuns)
- [Privacidade](#privacidade)
- [Desenvolvimento](#desenvolvimento)
- [Licença](#licença)

---

## Instalação

Você precisa do **aplicativo do Discord** instalado no computador. A versão do navegador não serve.

### Windows

1. Baixe o `livedot.exe` da [versão mais recente](https://github.com/kahd0/livedot/releases/latest).
2. Abra o arquivo. Não precisa instalar nada.

> [!NOTE]
> O Windows pode mostrar o aviso **"O Windows protegeu o computador"**, porque o LiveDot não tem assinatura digital. Clique em **Mais informações** e depois em **Executar assim mesmo**.

### Linux

Precisa de Python 3.10 ou mais novo e de uma sessão **X11**.

```bash
git clone https://github.com/kahd0/livedot.git
cd livedot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
./livedot.sh
```

O LiveDot encontra o Discord instalado por pacote, Flatpak ou Snap.

---

## Primeira configuração

Você faz isso **uma vez só**, e leva uns 5 minutos.

O Discord só deixa um programa controlar o seu microfone se esse programa estiver registrado no portal de desenvolvedores, e só libera esse acesso para quem fez o registro. Por isso cada pessoa cria o seu próprio registro. É gratuito, e não precisa de bot nem de publicar nada.

### 1. Registre o LiveDot no Discord

1. Entre no [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications) com a sua conta e clique em **New Application**. Dê qualquer nome, como `LiveDot`, e aceite os termos.
2. No menu da esquerda, abra **OAuth2**.
3. Copie o **Client ID**.
4. Clique em **Reset Secret**, confirme e copie o **Client Secret**. Ele só aparece uma vez, então deixe-o à mão.
5. Em **Redirects**, clique em **Add Redirect**, digite `http://localhost` e clique em **Save Changes**.

### 2. Conecte o LiveDot

Ao abrir, o LiveDot aparece do lado esquerdo da tela como um anel cinza, porque ainda não está conectado.

1. Clique com o **botão direito** no anel e escolha **Configurar Discord…**.
2. No grupo **Discord**, cole o Client ID e o Client Secret e clique em **Conectar**.
3. O Discord abre um pedido de permissão. Clique em **Autorizar**.

<img src="manual/04_configuracao.png" width="420" alt="Janela de configurações do LiveDot">

Pronto! O status muda para **Conectado** e o ponto passa a mostrar o seu microfone. Daqui em diante, o LiveDot conecta sozinho sempre que o Discord estiver aberto.

> [!TIP]
> Arraste o ponto para onde preferir e marque **Inicializar com sistema** no menu do botão direito. Assim ele abre junto com o computador e você não precisa pensar nele de novo.

---

## Como usar

### O que o ponto mostra

| | Estado | O que significa |
|:-:|---|---|
| <img src="manual/estado_fechado.png" width="64" alt=""> | **Microfone fechado** | Ninguém te ouve. |
| <img src="manual/estado_aberto.png" width="64" alt=""> | **Microfone aberto** | Estão te ouvindo. O ponto "respira" para chamar a sua atenção. |
| <img src="manual/estado_ensurdecido.png" width="64" alt=""> | **Ensurdecido** | Você não ouve ninguém e ninguém te ouve. |
| <img src="manual/estado_fora_de_chamada.png" width="64" alt=""> | **Fora de chamada** | Você não está em nenhum canal de voz, então o microfone não importa. |
| <img src="manual/estado_desconectado.png" width="64" alt=""> | **Desconectado** | O LiveDot não está falando com o Discord. Veja [Problemas comuns](#problemas-comuns). |
| <img src="manual/estado_mensagem_direta.png" width="64" alt=""> | **Mensagem para você** | Chegou uma mensagem direta ou uma menção a você. |
| <img src="manual/estado_mensagem.png" width="64" alt=""> | **Outra mensagem** | Chegou mensagem num canal em que o Discord te notifica. |
| <img src="manual/estado_piscando.png" width="64" alt=""> | **Piscando em amarelo** | O LiveDot mutou você sozinho, você acabou de entrar numa chamada ou abriu o LiveDot de novo. |

O vermelho só aparece com o microfone aberto numa chamada. Nenhum outro aviso usa essa cor.

### Controles

| Faça isto | Para |
|---|---|
| **Clique** no ponto | Abrir ou fechar o microfone. |
| **Toque** no atalho *(padrão `Ctrl+Alt+M`)* | Abrir ou fechar o microfone de qualquer lugar, até dentro de um jogo em tela cheia. |
| **Segure** o atalho | Inverter só enquanto segura. Mutado, você fala enquanto segura. Aberto, o atalho vira um botão de tosse. |
| Clique com o **botão do meio** no ponto | Ensurdecer ou voltar a ouvir. |
| Clique na **bolinha azul** | Abrir no Discord a conversa da última mensagem. |
| **Passe o mouse** sobre o ponto com a bolinha acesa | Ver quem mandou a última mensagem e onde. |
| **Segure e arraste** o ponto | Mudar o ponto de lugar. |
| Clique com o **botão direito** | Abrir o menu. |

Abrir o microfone pelo ponto ou pelo atalho também tira o ensurdecer, como o botão do próprio Discord.

### Aviso de mensagens

A bolinha azul segue as suas configurações de notificação do Discord: ela só acende para o que o Discord te notificaria. Servidores e canais silenciados ficam de fora, e se a janela do Discord já estiver na frente, nada acende.

- Ela some quando a janela do Discord vem para a frente. O Discord não avisa quando uma mensagem é lida, então olhar o Discord é o que conta.
- Ela aparece com um pulinho e fica parada. Se passar 15 minutos sem você olhar, pulsa de novo de vez em quando.
- O texto da mensagem nunca aparece, para não vazar num compartilhamento de tela.

### Proteções do microfone

- **Entrar em chamadas já mutado:** ao entrar num canal de voz, ou trocar de canal, o LiveDot fecha o microfone na hora e pisca uma vez.
- **Mutar microfone esquecido:** se o microfone ficar aberto numa chamada por 5 minutos sem transmitir nada, o LiveDot fecha e pisca três vezes. O Discord conta como fala qualquer som acima da sensibilidade do microfone, então barulho alto também reinicia a contagem.

As duas podem ser ajustadas ou desligadas em **Configurações**.

---

## Personalizando

Clique com o botão direito no ponto para abrir o menu.

<img src="manual/03_botao_direito.png" width="300" alt="Menu do botão direito do LiveDot">

| No menu | Para quê |
|---|---|
| **Configurações** | Todas as opções abaixo, e a conexão com o Discord. |
| **Travar posição** | Evitar mover o ponto sem querer. |
| **Definir atalho** | Escolher o atalho global. |
| **Opacidade** e **Tamanho** | Ajustes rápidos da aparência. |
| **Inicializar com sistema** | Abrir o LiveDot junto com o computador. |
| **Sair** | Fechar o LiveDot. |

Em **Configurações**:

| Opção | Padrão | O que faz |
|---|---|---|
| Tamanho | 100% | De 50% a 200%, para telas grandes ou pequenas. |
| Opacidade base | 100% | Deixa o ponto mais transparente em todos os estados. |
| Travar posição na tela | desligado | O mesmo do menu. |
| Iniciar junto com o sistema | desligado | O mesmo do menu. |
| Entrar em chamadas já mutado | ligado | Veja [Proteções do microfone](#proteções-do-microfone). |
| Mutar mic aberto sem falar após | 5 min | De 1 a 60 minutos, ou `nunca` para desligar. |
| Atalho do Livedot | `Ctrl+Alt+M` | Veja a dica abaixo. |

**Dica de atalho:** um botão lateral do mouse (`Mouse8` ou `Mouse9`) é o jeito mais confortável, porque você não tira a mão do mouse. Também vale qualquer tecla junto com `Ctrl`, `Alt`, `Shift` ou `Super`, ou uma tecla de `F1` a `F24` sozinha. Uma tecla comum sem modificador não é aceita, porque ela pararia de funcionar no resto do sistema.

---

## Problemas comuns

Quando o ponto vira um **anel cinza**, o motivo aparece no topo do menu do botão direito, marcado com ⚠.

| Mensagem | O que fazer |
|---|---|
| *Discord fechado* | Abra o Discord. O LiveDot reconecta sozinho em poucos segundos. |
| *Discord não configurado* | Siga a [Primeira configuração](#primeira-configuração). |
| *Autorização negada* ou *necessária* | Em **Configurações**, clique em **Conectar** e depois em **Autorizar** no Discord. |
| *Invalid Client ID* | Confira o Client ID copiado do portal. |
| *Falha ao obter acesso* | Confira o Client Secret. Se você gerou outro no portal, cole o novo. Se a mensagem citar `redirect_uri`, adicione `http://localhost` em **Redirects**. |
| *Atalho já usado por outro programa* | Escolha outra combinação em **Definir atalho**. |

**Não acha o ponto?** Abra o LiveDot de novo. O ponto que já está aberto pisca em amarelo e, se estiver fora da tela, volta para o monitor principal.

**O Discord pediu autorização de novo depois de atualizar.** É normal: o aviso de mensagens precisa de uma permissão a mais. Se você recusar, o resto continua funcionando, só sem a bolinha azul.

**A bolinha azul não aparece.** Ela só acende para o que o Discord notificaria. Confira as notificações daquele servidor ou canal no Discord. Se você recusou a permissão extra, clique em **Conectar** em **Configurações** e autorize.

**O microfone mutou sozinho.** Foi uma das [proteções do microfone](#proteções-do-microfone). Ajuste ou desligue em **Configurações**.

**O atalho não funciona no Linux.** O atalho global precisa de uma sessão X11. Em Wayland puro ele não funciona, mas o clique no ponto continua funcionando.

---

## Privacidade

- O LiveDot conversa com o aplicativo do Discord **dentro do seu computador**. A única conexão com a internet é com o `discord.com`, para obter e renovar a autorização.
- Ele **não acessa o áudio** do microfone. Só lê e muda as configurações de voz do Discord.
- Das notificações, ele usa só o título, com quem mandou e onde. O texto das mensagens não é exibido nem gravado.
- O Client Secret e a autorização ficam no arquivo de configuração, no seu computador. Não compartilhe esse arquivo.
- Para cortar o acesso a qualquer momento, abra **Configurações de usuário → Aplicativos autorizados** no Discord e remova o app que você criou.

| Onde fica | Linux | Windows |
|---|---|---|
| Configuração | `~/.config/livedot/config.json` | `%APPDATA%\Livedot\config.json` |
| Log | `~/.config/livedot/logs/livedot.log` | `%APPDATA%\Livedot\logs\livedot.log` |

---

## Desenvolvimento

### Rodando a partir do código

No Linux, siga a [instalação](#linux). No Windows:

```powershell
git clone https://github.com/kahd0/livedot.git
cd livedot
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python livedot.py
```

O log, citado em [Privacidade](#privacidade), registra conexão, atalho, proteções e avisos, e é o primeiro lugar para investigar um problema.

### Como o código está organizado

| Arquivo | Responsabilidade |
|---|---|
| `livedot.py` | Ponto de entrada, janela do ponto, desenho e menu. |
| `state_manager.py` | Estado exibido, animações e arquivo de configuração. |
| `discord_rpc.py` | Conexão com o Discord pela RPC local e autorização OAuth2. |
| `mic_guard.py` | Entrar mutado, microfone esquecido e tocar/segurar o atalho. |
| `message_alert.py` | Bolinha de mensagens. |
| `focus.py` | Saber se o Discord está na frente e trazê-lo para a frente. |
| `input_manager.py` | Atalho global, com `input_x11.py` para Linux e `input_win32.py` para Windows. |
| `settings_dialog.py` | Janela de configurações e captura do atalho. |
| `autostart.py` | Iniciar junto com o sistema. |
| `constants.py` | Cores, tamanhos, tempos e valores padrão. |

O Discord é a única fonte da verdade: o clique e o atalho só pedem a mudança, e o ponto muda quando o Discord confirma.

### Publicando uma versão

Envie uma tag que comece com `v`:

```bash
git tag -a v2.2.0 -m "v2.2.0"
git push origin v2.2.0
```

O GitHub Actions gera o `livedot.exe` e o anexa à release da tag. Para gerar o `.exe` na sua máquina Windows:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name livedot --exclude-module Xlib --exclude-module input_x11 livedot.py
```

---

## Licença

[MIT](LICENSE): use, modifique e distribua à vontade, inclusive em outros projetos, desde que mantenha o aviso de autoria. O LiveDot é oferecido como está, sem garantia.
