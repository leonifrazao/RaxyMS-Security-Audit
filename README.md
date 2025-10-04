# Raxy Farm

**Raxy Farm** é uma solução completa para automação e gerenciamento de contas Microsoft Rewards. O projeto é composto por um backend robusto em Python que realiza as automações e uma interface de painel de controle (dashboard) moderna e reativa para monitoramento e operação.

## ✨ Principais Funcionalidades

### Backend (`raxy_project`)

  - **Executor em Lote:** Processa múltiplas contas em paralelo usando `ThreadPoolExecutor`, otimizando o tempo de execução.
  - **Gerenciamento de Proxy:** Integração com Xray/V2Ray para testar, rotacionar e gerenciar proxies, garantindo a conectividade das contas.
  - **Fontes de Dados Flexíveis:** Suporte para carregar contas a partir de arquivos de texto (`users.txt`) ou de um banco de dados (configurado para **Supabase**).
  - **Arquitetura Limpa:** Código modularizado com injeção de dependências, separando responsabilidades entre serviços, repositórios e domínio.
  - **API RESTful:** Uma API FastAPI (`/api/v1`) expõe todas as funcionalidades do backend, permitindo a comunicação com o dashboard ou outros clientes.
  - **CLI Robusta:** Uma interface de linha de comando com `Typer` para executar o farm, testar proxies e listar contas diretamente do terminal.
  - **Logging Estruturado:** Utiliza a biblioteca `rich` para logs coloridos e contextuais, facilitando a depuração e o monitoramento.

### Frontend (`raxy-dashboard`)

  - **Painel de Controle Reativo:** Dashboard construído com **Next.js (App Router)** e **React** para visualização de dados em tempo real.
  - **Visualização de Contas:** Tabela detalhada com busca, filtragem por fonte (arquivo/banco de dados) e seleção de contas.
  - **Métricas e KPIs:** Exibição de indicadores-chave de performance, como total de contas, pontos acumulados e farms ativos.
  - **Gerenciamento de Operações:** Permite adicionar novas contas, iniciar o farm para todas as contas elegíveis e executar farms individuais.
  - **UI Moderna:** Interface construída com **Tailwind CSS** e **shadcn/ui**, oferecendo uma experiência de usuário limpa, responsiva e com suporte a temas (claro/escuro).
  - **Data Fetching Eficiente:** Utiliza **React Query (TanStack Query)** para gerenciar o estado do servidor, cache e revalidação de dados da API.

## 🏗️ Arquitetura

O projeto segue uma arquitetura de monorepo, dividida em duas partes principais:

1.  **`raxy_project/` (Backend):**

      - Um **monolito modular** em Python.
      - **`app/`**: Camada da API **FastAPI**, responsável por expor os endpoints HTTP. Atua como um gateway para os serviços principais.
      - **`raxy/`**: O core da aplicação, contendo a lógica de negócio. É estruturado com base em princípios de arquitetura limpa e injeção de dependências:
          - **`domain/`**: Entidades centrais (ex: `Conta`).
          - **`interfaces/`**: Contratos (interfaces abstratas) para serviços e repositórios.
          - **`services/`**: Implementações da lógica de negócio (autenticação, execução, etc.).
          - **`repositories/`**: Implementações para acesso a dados (arquivos, banco de dados).
          - **`api/`**: Clientes para APIs externas (Bing, Supabase).
          - **`container.py`**: Container de injeção de dependências que conecta as interfaces às suas implementações.

2.  **`raxy-dashboard/` (Frontend):**

      - Uma aplicação web moderna construída com **Next.js** e o **App Router**.
      - **`src/app/`**: Estrutura de rotas principal.
      - **`src/components/`**: Componentes React reutilizáveis, incluindo a biblioteca de UI `shadcn/ui`.
      - **`src/features/`**: Lógica de UI e estado específicos para cada funcionalidade (ex: `accounts`, `dashboard`).
      - **`src/lib/` e `src/hooks/`**: Utilitários, hooks personalizados e clientes de API para comunicação com o backend.
      - **`src/providers/`**: Provedores de contexto globais (Tema, React Query).

## 🛠️ Tecnologias Utilizadas

| Backend (`raxy_project`) | Frontend (`raxy-dashboard`) |
| ------------------------ | ----------------------------- |
| Python 3.11+             | TypeScript                    |
| FastAPI                  | Next.js 15+ (App Router)      |
| Typer (CLI)              | React 19+                     |
| Botasaurus               | Tailwind CSS                  |
| Supabase (Cliente DB)    | shadcn/ui                     |
| Rich (Logging)           | React Query (TanStack Query)  |
| SQLAlchemy (Opcional)    | Zustand (State Management)    |
| Xray/V2Ray (via `Proxy`) | Zod (Validação)               |
| pydantic                 | Lucide Icons                  |

## 🚀 Configuração e Instalação

### Pré-requisitos

  - Python 3.11+
  - Node.js 18+
  - `pnpm` (ou `npm`/`yarn`)
  - Um executável do **Xray** ou **V2Ray** no `PATH` do sistema (usado pelo `raxy/api/proxy/manager.py`).

### 1\. Backend (`raxy_project`)

1.  **Navegue até a pasta do backend:**

    ```bash
    cd raxy_project
    ```

2.  **Crie e ative um ambiente virtual:**

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    ```

3.  **Instale as dependências Python:**

    ```bash
    pip install -r requirements.txt 
    ```

    *(Nota: Se o `requirements.txt` não existir, instale as dependências principais: `fastapi uvicorn python-dotenv botasaurus supabase rich typer random-user-agent`)*

4.  **Configure as variáveis de ambiente:**

      - Crie um arquivo `.env` na raiz de `raxy_project/`.
      - Adicione as credenciais do Supabase se for usar o banco de dados:
        ```env
        SUPABASE_URL="https://your-project-ref.supabase.co"
        SUPABASE_KEY="your-supabase-anon-key"
        ```

5.  **Configure as contas (se usar arquivo):**

      - Crie um arquivo `users.txt` na raiz de `raxy_project/`.
      - Adicione as contas no formato `email:senha`, uma por linha.

### 2\. Frontend (`raxy-dashboard`)

1.  **Navegue até a pasta do frontend:**

    ```bash
    cd raxy-dashboard
    ```

2.  **Instale as dependências Node.js:**

    ```bash
    pnpm install
    ```

3.  **Configure as variáveis de ambiente:**

      - Crie um arquivo `.env.local` na raiz de `raxy-dashboard/`.
      - Adicione a URL da API do backend:
        ```env
        NEXT_PUBLIC_RAXY_API_URL="http://127.0.0.1:8000"
        ```

## ▶️ Como Executar

### 1\. Iniciar o Backend

Você pode iniciar o backend de duas formas: como servidor API ou via CLI.

**Opção A: Iniciar o Servidor API (para usar com o Dashboard)**

Na pasta `raxy_project/`, execute:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

A API estará disponível em `http://127.0.0.1:8000`.

**Opção B: Usar a Interface de Linha de Comando (CLI)**

A CLI é poderosa para executar tarefas diretamente. Na pasta `raxy_project/`:

  - **Executar o farm (usando `users.txt`):**

    ```bash
    python cli.py run
    ```

  - **Executar o farm (usando o banco de dados):**

    ```bash
    python cli.py run --source database
    ```

  - **Testar proxies:**

    ```bash
    python cli.py proxy test --threads 20 --country US
    ```

  - **Listar contas do arquivo:**

    ```bash
    python cli.py accounts list-file
    ```

### 2\. Iniciar o Frontend

Com o servidor do backend em execução, inicie o dashboard:

1.  Navegue até a pasta `raxy-dashboard/`.
2.  Execute o servidor de desenvolvimento:
    ```bash
    pnpm dev
    ```
3.  Abra **http://localhost:3000** em seu navegador para acessar o Raxy Farm Dashboard.