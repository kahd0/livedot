# LiveDot

Um ponto discreto que fica sempre por cima de todas as janelas e mostra, num relance, se o seu microfone no Discord está aberto ou fechado — e permite ligar/desligar com um clique ou um atalho, mesmo com o Discord minimizado.

O LiveDot conversa direto com o aplicativo do Discord pela conexão local que ele oferece (RPC). Por isso o ponto mostra sempre o estado **real** do microfone: se você mutar pelo botão ou pelos atalhos do próprio Discord, o ponto acompanha.

---

## Como funciona, em uma frase

O ponto espelha o mudo do Discord; clicar nele (ou usar o atalho do LiveDot) pede ao Discord para alternar o microfone, e o ponto muda assim que o Discord confirma.

---

## Usando o aplicativo

### 1. Ao iniciar

![Ponto ao iniciar](manual/01_iniciar.png)

Ao abrir a aplicação, aparece um ponto pequeno e discreto, por padrão perto do canto inferior esquerdo do monitor. Com o microfone **fechado** (mudo), o ponto é pequeno, azul-escuro e com pouca opacidade — quase invisível.

Ele não tem janela, não aparece na barra de tarefas e fica sempre acima de todas as outras janelas.

Enquanto o LiveDot não está conectado ao Discord — Discord fechado, ainda não configurado ou aguardando autorização — o ponto aparece como um **anel cinza vazado**. Quando o Discord abre, ele reconecta sozinho em poucos segundos.

### 2. Clicando no ponto

![Ponto ativo](manual/02_clicando.png)

Um clique com o **botão esquerdo** pede ao Discord para alternar o microfone. No estado **aberto**, o ponto:

- fica vermelho e maior;
- faz uma animação rápida de expansão ao ativar;
- passa a "respirar" (oscila suavemente de tamanho e opacidade), o que torna impossível não notar de canto de olho.

Se você estiver **ensurdecido** no Discord, o ponto aparece fechado; abrir o microfone pelo ponto também tira o ensurdecer, igual ao botão do próprio Discord.

Clicar no anel cinza (desconectado) faz o LiveDot tentar conectar de novo na hora.

> **Arrastar em vez de clicar:** para mover o ponto, segure o botão esquerdo por ~0,3 s e arraste pelo menos 5 px. Cliques rápidos alternam o microfone; arrastos movem e salvam a nova posição. Com a posição travada, o arrasto é ignorado — e também não conta como clique.

### 3. Menu de botão direito

![Menu de contexto](manual/03_botao_direito.png)

O **botão direito** abre o menu com os ajustes de acesso rápido:

| Item | O que faz |
|---|---|
| **Configurações** | Abre a janela completa de configurações (próxima seção). |
| **Travar posição** | Impede mover o ponto sem querer. Marque depois de posicioná-lo onde quer. |
| **Definir atalho** | Define o atalho global do LiveDot (tecla ou botão lateral do mouse). |
| **Opacidade** ▸ | Atalhos de 20%, 40%, 60%, 80% ou 100%. |
| **Tamanho** ▸ | Pequeno (75%), Padrão (100%), Grande (150%) ou Gigante (200%). |
| **Inicializar com sistema** | Registra o LiveDot para abrir junto com a sessão do usuário. |
| **Sair** | Encerra a aplicação. |

Quando algo impede o funcionamento — Discord fechado, não configurado ou sem autorização, ou um atalho recusado pelo sistema — o topo do menu mostra um aviso ⚠ com o motivo e, quando faz sentido, a opção **Conectar ao Discord**.

### 4. Configurações

![Janela de configurações](manual/04_configuracao.png)

#### Aparência

- **Tamanho (Escala)** — de 50% a 200%. Multiplica o tamanho do ponto em todos os estados. Útil para telas grandes ou pequenas; a mudança é aplicada na hora.
- **Opacidade Base** — de 10% a 100%. É um multiplicador aplicado sobre a opacidade de cada estado (o estado fechado já é naturalmente mais transparente que o aberto). Baixe se quiser um ponto mais discreto; suba se ele estiver sobre um fundo claro.

#### Comportamento

- **Travar posição na tela** — mesma opção do menu de contexto. Com ela ligada o ponto não se move, mesmo que você arraste em cima dele.
- **Iniciar junto com o sistema** — no Linux cria uma entrada em `~/.config/autostart/livedot.desktop`; no Windows grava um valor em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Se você mudar o LiveDot de pasta ou baixar uma versão nova em outro lugar, a entrada é atualizada sozinha na próxima vez que ele abrir.

#### Atalho

- **Atalho do Livedot** *(padrão `Ctrl+Alt+M`)* — aperte-o em qualquer lugar do sistema para alternar o microfone, mesmo com o Discord minimizado ou em cima de um jogo em tela cheia.

Clique em **Definir** e pressione a combinação desejada; `Esc` cancela. Vale:

- qualquer tecla junto com `Ctrl`, `Alt`, `Shift` ou `Super`;
- as teclas `F1`–`F24` sozinhas;
- os **botões laterais do mouse**: `Mouse8` (voltar), `Mouse9` (avançar) e `Mouse10` (apenas no Linux), com ou sem modificador.

Uma tecla comum sem modificador é recusada, porque ela deixaria de funcionar no sistema inteiro. Usar `Mouse8` é o jeito mais confortável de alternar o microfone sem tirar a mão do mouse.

#### Discord

Onde ficam o **Client ID** e o **Client Secret** do seu aplicativo do Discord (veja a próxima seção), o status da conexão e o botão **Conectar**.

---

## Conectando ao Discord (uma vez só)

O Discord só deixa um programa controlar o microfone se ele se identificar com um aplicativo registrado no portal de desenvolvedores. Como o LiveDot é de uso pessoal, você cria o seu próprio — leva uns 5 minutos e não precisa de bot nem de publicar nada.

1. **Crie o aplicativo.** Entre em [discord.com/developers/applications](https://discord.com/developers/applications), clique em **New Application** e dê um nome (por exemplo, `LiveDot`).
2. **Pegue as credenciais.** No menu **OAuth2**:
   - copie o **Client ID**;
   - clique em **Reset Secret** e copie o **Client Secret** (ele só aparece uma vez);
   - em **Redirects**, adicione `http://localhost` e salve.
3. **Cole no LiveDot.** Botão direito no ponto → **Configurações** → grupo **Discord**: cole o Client ID e o Client Secret e clique em **Conectar**.
4. **Autorize no Discord.** O Discord abre uma janela pedindo permissão para o aplicativo acessar suas configurações de voz. Clique em **Autorizar**.
5. **Pronto.** O status muda para *Conectado* e o ponto passa a mostrar o microfone de verdade.

A partir daí o LiveDot conecta sozinho toda vez que o Discord estiver aberto, e renova o acesso automaticamente quando ele expira (a cada ~7 dias). O pedido de autorização só volta a aparecer se o acesso for revogado.

Observações:

- Sem aprovação da Discord, só o dono do aplicativo (e testers cadastrados nele) pode autorizá-lo. Se outra pessoa quiser usar o LiveDot, ela cria o próprio aplicativo.
- O Client Secret e o token ficam apenas no `config.json` local (no Linux, legível só pelo seu usuário). Não compartilhe esse arquivo.
- Se você usava uma versão antiga do LiveDot, que simulava um atalho do Discord (por exemplo `Ctrl+Shift+F12` em *Atalhos de teclado*), pode remover esse atalho do Discord: ele não é mais usado.
- Funciona com o Discord instalado normalmente, via Flatpak ou via Snap.

---

## Instalação

### Windows

Baixe o `livedot.exe` mais recente na página de [Releases](https://github.com/kahd0/livedot/releases) e execute — não precisa instalar nada.

### Linux (a partir do código)

```bash
git clone https://github.com/kahd0/livedot.git
cd livedot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
./livedot.sh
```

Requer Python 3.10+ e uma sessão **X11** (o atalho global usa grabs do X11; em sessões Wayland puras ele não funciona).

---

## Onde ficam os arquivos

| | Linux | Windows |
|---|---|---|
| Configuração | `~/.config/livedot/config.json` | `%APPDATA%\Livedot\config.json` |
| Log | `~/.config/livedot/logs/livedot.log` | `%APPDATA%\Livedot\logs\livedot.log` |

O log é rotacionado sozinho (até ~512 KB, mais um arquivo de backup). Só roda uma instância por vez: abrir o LiveDot de novo com ele já aberto faz o ponto piscar com um anel âmbar, o que ajuda a encontrá-lo.

---

## Problemas comuns

O motivo aparece no aviso ⚠ do menu de botão direito e no status das Configurações:

| Aviso | O que fazer |
|---|---|
| *Discord fechado* | Abra o Discord; o LiveDot reconecta sozinho. |
| *Discord não configurado* | Siga [Conectando ao Discord](#conectando-ao-discord-uma-vez-só). |
| *Autorização negada* / *Autorização necessária* | Configurações → **Conectar**, e clique em **Autorizar** na janela do Discord. |
| *Discord recusou a conexão: Invalid Client ID* | Confira o Client ID colado nas Configurações. |
| *Falha ao obter acesso: HTTP 401 …invalid_client…* | Confira o Client Secret. Se você gerou um novo no portal, o antigo deixou de valer: cole o novo. |
| *Falha ao obter acesso: …redirect_uri…* | Adicione `http://localhost` em **OAuth2 → Redirects** no portal. |
| *o atalho '…' já é usado por outro programa* | Escolha outra combinação em **Definir atalho**. |

- **O ponto sumiu** — abra o LiveDot de novo: o ponto pisca com um anel âmbar, em opacidade total, e volta para a tela principal se estiver fora da área visível. Se ele estiver com opacidade muito baixa sobre um fundo claro, ajuste pelo menu. Se o monitor onde ele estava foi desconectado, ele volta sozinho para a tela principal. Em último caso, apague as linhas `position_x` e `position_y` do `config.json` (não apague o arquivo inteiro, ou você perde as credenciais do Discord).
