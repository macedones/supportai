// ============================================================
// SupportAI Widget — <assistant-ai>
//
// Web Component standalone, sem dependencias externas.
// Embeda o especialista virtual de um projeto em qualquer site.
//
// Uso:
//   <script src="https://.../widget.js"></script>
//   <assistant-ai
//     project="erp-hospitalar"
//     api-url="https://api.suportai.exemplo.com"
//   ></assistant-ai>
//
// Atributos:
//   project   (obrigatorio) — slug do projeto (project_slug na API)
//   api-url   (obrigatorio) — URL base da API (sem barra final)
//   position  (opcional)    — "bottom-right" (padrao) | "bottom-left"
//   color     (opcional)    — cor de destaque (padrao: #6d4aff)
//   greeting  (opcional)    — mensagem inicial do assistente
// ============================================================

const STORAGE_KEY_PREFIX = "assistant_ai_session_";

class AssistantAI extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.aberto = false;
    this.mensagens = [];
    this.carregando = false;
  }

  connectedCallback() {
    this.projectSlug = this.getAttribute("project");
    this.apiUrl = (this.getAttribute("api-url") || "").replace(/\/$/, "");
    this.position = this.getAttribute("position") || "bottom-right";
    this.color = this.getAttribute("color") || "#6d4aff";
    this.greeting =
      this.getAttribute("greeting") ||
      "Ola! Sou o assistente virtual deste sistema. Como posso ajudar?";

    if (!this.projectSlug || !this.apiUrl) {
      console.error(
        "[assistant-ai] Atributos obrigatorios ausentes: 'project' e 'api-url'."
      );
      return;
    }

    this.sessionId = this._obterOuCriarSessionId();
    this._render();
  }

  // ----------------------------------------------------------
  // Sessao: persistida em localStorage por projeto, para que
  // o historico da conversa sobreviva a reload da pagina.
  // ----------------------------------------------------------
  _obterOuCriarSessionId() {
    const chave = STORAGE_KEY_PREFIX + this.projectSlug;
    try {
      let id = localStorage.getItem(chave);
      if (!id) {
        id = "sess_" + crypto.randomUUID();
        localStorage.setItem(chave, id);
      }
      return id;
    } catch {
      // localStorage pode estar bloqueado (modo privado, iframe sandboxed)
      return "sess_" + crypto.randomUUID();
    }
  }

  // ----------------------------------------------------------
  // Render inicial: estrutura HTML + estilos (Shadow DOM,
  // isolado do CSS do site host).
  // ----------------------------------------------------------
  _render() {
    const lado = this.position === "bottom-left" ? "left" : "right";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          all: initial;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        * { box-sizing: border-box; }

        .launcher {
          position: fixed;
          bottom: 20px;
          ${lado}: 20px;
          width: 60px;
          height: 60px;
          border-radius: 50%;
          background: ${this.color};
          color: white;
          border: none;
          cursor: pointer;
          box-shadow: 0 4px 14px rgba(0,0,0,0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
          z-index: 999999;
          transition: transform 0.15s ease;
        }
        .launcher:hover { transform: scale(1.05); }

        .panel {
          position: fixed;
          bottom: 90px;
          ${lado}: 20px;
          width: 360px;
          max-width: calc(100vw - 40px);
          height: 520px;
          max-height: calc(100vh - 120px);
          background: #ffffff;
          border-radius: 12px;
          box-shadow: 0 8px 30px rgba(0,0,0,0.2);
          display: none;
          flex-direction: column;
          overflow: hidden;
          z-index: 999999;
        }
        .panel.aberto { display: flex; }

        .header {
          background: ${this.color};
          color: white;
          padding: 14px 16px;
          font-weight: 600;
          font-size: 15px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .header button {
          background: none;
          border: none;
          color: white;
          font-size: 20px;
          cursor: pointer;
          line-height: 1;
          padding: 0;
        }

        .mensagens {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          background: #f7f7f9;
        }

        .msg {
          max-width: 85%;
          padding: 8px 12px;
          border-radius: 10px;
          font-size: 13px;
          line-height: 1.45;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
        .msg.usuario {
          align-self: flex-end;
          background: ${this.color};
          color: white;
          border-bottom-right-radius: 2px;
        }
        .msg.assistente {
          align-self: flex-start;
          background: white;
          color: #222;
          border: 1px solid #e3e3e8;
          border-bottom-left-radius: 2px;
        }
        .msg.erro {
          align-self: flex-start;
          background: #ffe9e9;
          color: #a33;
          border: 1px solid #f3c2c2;
        }

        .fontes {
          margin-top: 6px;
          padding-top: 6px;
          border-top: 1px solid #eee;
          font-size: 11px;
          color: #888;
        }
        .fontes b { color: #666; }

        .digitando {
          align-self: flex-start;
          font-size: 12px;
          color: #999;
          padding: 4px 12px;
          font-style: italic;
        }

        .input-area {
          display: flex;
          border-top: 1px solid #e3e3e8;
          padding: 8px;
          gap: 8px;
          background: white;
        }
        .input-area input {
          flex: 1;
          border: 1px solid #ddd;
          border-radius: 8px;
          padding: 8px 10px;
          font-size: 13px;
          outline: none;
          font-family: inherit;
        }
        .input-area input:focus { border-color: ${this.color}; }
        .input-area button {
          background: ${this.color};
          color: white;
          border: none;
          border-radius: 8px;
          padding: 0 14px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
        }
        .input-area button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      </style>

      <button class="launcher" aria-label="Abrir chat de suporte">💬</button>

      <div class="panel">
        <div class="header">
          <span>Assistente Virtual</span>
          <button class="fechar" aria-label="Fechar">✕</button>
        </div>
        <div class="mensagens"></div>
        <div class="input-area">
          <input type="text" placeholder="Digite sua pergunta..." />
          <button class="enviar">Enviar</button>
        </div>
      </div>
    `;

    this._elLauncher = this.shadowRoot.querySelector(".launcher");
    this._elPanel = this.shadowRoot.querySelector(".panel");
    this._elFechar = this.shadowRoot.querySelector(".fechar");
    this._elMensagens = this.shadowRoot.querySelector(".mensagens");
    this._elInput = this.shadowRoot.querySelector(".input-area input");
    this._elEnviar = this.shadowRoot.querySelector(".input-area button.enviar");

    this._elLauncher.addEventListener("click", () => this._toggle());
    this._elFechar.addEventListener("click", () => this._toggle(false));
    this._elEnviar.addEventListener("click", () => this._enviarMensagem());
    this._elInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._enviarMensagem();
    });

    // Mensagem de boas-vindas (apenas local, nao chama a API)
    this._adicionarMensagem("assistente", this.greeting);
  }

  _toggle(forcar) {
    this.aberto = typeof forcar === "boolean" ? forcar : !this.aberto;
    this._elPanel.classList.toggle("aberto", this.aberto);
    if (this.aberto) {
      this._elInput.focus();
    }
  }

  _adicionarMensagem(papel, texto, fontes) {
    const div = document.createElement("div");
    div.className = `msg ${papel}`;
    div.textContent = texto;

    if (fontes && fontes.length > 0) {
      const fontesDiv = document.createElement("div");
      fontesDiv.className = "fontes";
      const nomes = [...new Set(fontes.map((f) => f.documento_nome))];
      fontesDiv.innerHTML = `<b>Fontes:</b> ${nomes.join(", ")}`;
      div.appendChild(fontesDiv);
    }

    this._elMensagens.appendChild(div);
    this._elMensagens.scrollTop = this._elMensagens.scrollHeight;
  }

  _mostrarDigitando(mostrar) {
    let el = this.shadowRoot.querySelector(".digitando");
    if (mostrar) {
      if (!el) {
        el = document.createElement("div");
        el.className = "digitando";
        el.textContent = "Digitando...";
        this._elMensagens.appendChild(el);
      }
    } else if (el) {
      el.remove();
    }
    this._elMensagens.scrollTop = this._elMensagens.scrollHeight;
  }

  async _enviarMensagem() {
    const texto = this._elInput.value.trim();
    if (!texto || this.carregando) return;

    this._elInput.value = "";
    this._adicionarMensagem("usuario", texto);

    this.carregando = true;
    this._elEnviar.disabled = true;
    this._mostrarDigitando(true);

    try {
      const resp = await fetch(`${this.apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_slug: this.projectSlug,
          message: texto,
          session_id: this.sessionId,
        }),
      });

      const dados = await resp.json();

      this._mostrarDigitando(false);

      if (!resp.ok) {
        this._adicionarMensagem(
          "erro",
          dados.erro || "Ocorreu um erro ao processar sua pergunta."
        );
        return;
      }

      this._adicionarMensagem("assistente", dados.resposta, dados.fontes);
    } catch (err) {
      this._mostrarDigitando(false);
      this._adicionarMensagem(
        "erro",
        "Nao foi possivel conectar ao servidor. Verifique sua conexao."
      );
      console.error("[assistant-ai] Erro ao chamar /api/chat:", err);
    } finally {
      this.carregando = false;
      this._elEnviar.disabled = false;
    }
  }
}

customElements.define("assistant-ai", AssistantAI);
