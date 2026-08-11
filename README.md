# LiveDot

Um ponto discreto que fica sempre por cima de todas as janelas e mostra, num relance, se o seu microfone está aberto ou fechado — e permite ligar/desligar com um clique, mesmo com o Discord minimizado.

Foi feito pensando no Discord, mas **não tem nenhum vínculo com ele**: o LiveDot apenas dispara um atalho de teclado global. Serve para qualquer programa que aceite atalhos globais (OBS, Teams, Mumble, TeamSpeak, etc.).

---

## Como funciona, em uma frase

O LiveDot mantém um estado visual (ponto apagado = fechado / ponto vermelho = aberto) e, **toda vez que esse estado muda**, ele envia ao sistema o atalho de teclado que você configurou — o mesmo atalho que o Discord está escutando para ativar/desativar o microfone.

---

## Usando o aplicativo

### 1. Ao iniciar

![Ponto ao iniciar](manual/01_iniciar.png)

Ao abrir a aplicação, aparece um ponto pequeno e discreto, por padrão perto do canto inferior esquerdo do monitor. Esse é o estado **fechado** (mudo): ponto pequeno, azul-escuro e com pouca opacidade — quase invisível.

Ele não tem janela, não aparece na barra de tarefas e fica sempre acima de todas as outras janelas.

### 2. Clicando no ponto

![Ponto ativo](manual/02_clicando.png)

Um clique com o **botão esquerdo** alterna o estado. No estado **aberto**, o ponto:

- fica vermelho e maior;
- faz uma animação rápida de expansão ao ativar;
- passa a "respirar" (oscila suavemente de tamanho e opacidade), o que torna impossível não notar de canto de olho.

No mesmo instante, o atalho configurado é enviado ao sistema — é isso que ativa/desativa o microfone no Discord.

> **Arrastar em vez de clicar:** para mover o ponto, segure o botão esquerdo por ~0,3 s e arraste pelo menos 5 px. Cliques rápidos alternam o estado; arrastos movem e salvam a nova posição. Com a posição travada, o arrasto é ignorado.

### 3. Menu de botão direito

![Menu de contexto](manual/03_botao_direito.png)

O **botão direito** abre o menu com os ajustes de acesso rápido:

| Item | O que faz |
|---|---|
| **Configurações** | Abre a janela completa de configurações (próxima seção). |
| **Travar posição** | Impede mover o ponto sem querer. Marque depois de posicioná-lo onde quer. |
| **Alterar hotkey** ▸ | Define o *Atalho do Livedot* ou o *Atalho do Discord* direto pelo menu. |
| **Opacidade** ▸ | Atalhos de 20%, 40%, 60%, 80% ou 100%. |
| **Tamanho** ▸ | Pequeno (75%), Padrão (100%), Grande (150%) ou Gigante (200%). |
| **Inicializar com sistema** | Registra o LiveDot para abrir junto com a sessão do usuário. |
| **Sair** | Encerra a aplicação. |

Se algum atalho não puder ser registrado ou enviado (por exemplo, outro programa já usa a mesma combinação), aparece um aviso ⚠ no topo desse menu.

### 4. Configurações

![Janela de configurações](manual/04_configuracao.png)

#### Aparência

- **Tamanho (Escala)** — de 50% a 200%. Multiplica o tamanho do ponto em ambos os estados. Útil para telas grandes ou pequenas; a mudança é aplicada na hora.
- **Opacidade Base** — de 10% a 100%. É um multiplicador aplicado sobre a opacidade de cada estado (o estado fechado já é naturalmente mais transparente que o aberto). Baixe se quiser um ponto mais discreto; suba se ele estiver sobre um fundo claro.

#### Comportamento

- **Travar posição na tela** — mesma opção do menu de contexto. Com ela ligada o ponto não se move, mesmo que você arraste em cima dele.
- **Habilitar feedback sonoro** — reserva um bipe curto ao alternar (grave ao fechar, agudo ao abrir). *Observação: nesta versão a opção é salva, mas os tons ainda não são reproduzidos.*
- **Iniciar junto com o sistema** — no Linux cria uma entrada em `~/.config/autostart/livedot.desktop`; no Windows grava um valor em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

#### Atalhos do Teclado

Aqui está a parte mais importante — são **dois atalhos diferentes**, com papéis opostos:

- **Atalho do Livedot** *(padrão `Ctrl+Alt+M`)* — o atalho que o LiveDot **escuta**. Aperte-o em qualquer lugar do sistema e o ponto alterna de estado (o que, por consequência, também dispara o atalho do Discord).
- **Atalho do Discord** *(padrão `Ctrl+Shift+F12`)* — o atalho que o LiveDot **envia** ao sistema sempre que o estado muda. Precisa ser exatamente a mesma combinação registrada no Discord.

Clique em **Definir** e pressione a combinação desejada; `Esc` cancela. Além de teclas, a captura aceita os **botões laterais do mouse**: `Mouse8` (voltar), `Mouse9` (avançar) e `Mouse10` (apenas no Linux). Usar `Mouse8` como *Atalho do Livedot* é o jeito mais confortável de alternar o microfone sem tirar a mão do mouse.

Escolha para o *Atalho do Discord* uma combinação que você nunca usaria por acidente (`Ctrl+Shift+F12` é uma boa) — ela será apertada "por você" toda vez que o ponto mudar de estado.

---

## O fluxo completo com o Discord

Essa é a rotina para a qual o LiveDot foi feito:

1. **Posicione o ponto** em um lugar que fique sempre visível mas nunca atrapalhe. O ponto fica por cima de tudo, então o ideal é um canto morto — eu deixo em um trecho da barra de tarefas onde nunca aparecem ícones.
2. **Trave a posição** (menu de botão direito → *Travar posição*) para não movê-lo sem querer depois.
3. **Defina os atalhos** em *Configurações*: um *Atalho do Livedot* confortável para o dia a dia (uso `Mouse8`) e um *Atalho do Discord* fora do caminho (`Ctrl+Shift+F12`).
4. **No Discord**, vá em *Configurações do usuário → Atalhos de teclado*, adicione o atalho **Ativar/desativar mudo** e registre exatamente a mesma combinação do *Atalho do Discord*. Os atalhos do Discord são globais, então funcionam com ele minimizado.
5. **Sincronize os dois estados uma vez.** O LiveDot sempre abre no estado fechado (ponto apagado), e ele não consulta o Discord — apenas conta as alternâncias. Então, ao iniciar a sessão, deixe o microfone do Discord no mesmo estado que o ponto indica; se estiverem trocados, um clique no ponto realinha. Isso precisa ser feito uma vez a cada vez que você abre o Discord.

A partir daí:

- você **enxerga** o estado do microfone a qualquer momento, sem procurar a janela do Discord;
- você **alterna** o microfone clicando no ponto ou pelo *Atalho do Livedot*, mesmo com o Discord minimizado ou em cima de um jogo em tela cheia.

> **Por que a sincronização importa:** o LiveDot é um controle "às cegas" — ele envia o atalho e assume que o outro programa obedeceu. Se você alternar o mudo pela interface do Discord, os dois ficam invertidos até você clicar uma vez no ponto para reajustar.

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

Requer Python 3.10+ e uma sessão **X11** (o backend usa XTEST/Xlib; em sessões Wayland puras os atalhos globais não funcionam).

---

## Onde ficam os arquivos

| | Linux | Windows |
|---|---|---|
| Configuração | `~/.config/livedot/config.json` | `%APPDATA%\Livedot\config.json` |
| Log | `~/.config/livedot/logs/livedot.log` | `%APPDATA%\Livedot\logs\livedot.log` |

Só roda uma instância por vez; abrir o LiveDot novamente com ele já aberto simplesmente não faz nada.

---

## Problemas comuns

- **O ponto muda de cor mas o Discord não responde** — a combinação do *Atalho do Discord* não corresponde à registrada no Discord, ou o Discord está sendo executado como administrador enquanto o LiveDot não está (nesse caso o Windows bloqueia o envio; execute os dois no mesmo nível).
- **O atalho global não funciona** — outro programa já registrou a mesma combinação. Abra o menu de botão direito: o aviso ⚠ no topo mostra o motivo, e o log traz o texto completo.
- **O ponto sumiu** — pode estar com opacidade muito baixa sobre um fundo claro, ou fora da área visível se você mudou de monitor. Ajuste a opacidade pelo menu ou apague `config.json` para voltar à posição padrão.
