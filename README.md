# 🤖 Oracle AI --- Real-Time AI Voice Assistant

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LiveKit](https://img.shields.io/badge/LiveKit-Realtime-orange)
![Gemini](https://img.shields.io/badge/Gemini-LLM-green)
![Android](https://img.shields.io/badge/Android-Mobile-brightgreen)
![Status](https://img.shields.io/badge/Status-Production_Ready-success)

------------------------------------------------------------------------

## 🚀 Overview

Oracle is a real-time AI voice assistant built using **LiveKit Agents**, **Google Gemini Realtime**, and **Mem0 long-term memory**. It supports live voice conversations, tool execution such as weather updates, time queries, email drafting, and web search, along with persistent memory across sessions for contextual continuity. The system leverages low-latency streaming communication and a modular agent architecture to enable intelligent multi-turn interactions, integrating a Python backend with an Android client for a seamless AI-powered voice experience.


------------------------------------------------------------------------

## ✨ Features

-   🎙 Real-time voice interaction
-   🧠 Long-term memory (Mem0 integration)
-   🌦 Weather tool integration
-   ⏰ Accurate timezone-based time tool
-   📧 Email sending capability
-   🔎 Web search integration
-   📱 Android mobile connectivity
-   ☁️ LiveKit Cloud real-time streaming

------------------------------------------------------------------------

## 🛠 Tech Stack
### 💻 Backend (AI Agent)

-   Python 3.10+
-   LiveKit Agents SDK – Real-time agent framework
-   Google Gemini Realtime API – LLM for voice & text intelligence
-   Mem0 – Persistent long-term memory system
-   Requests – API calls (weather services)
-   smtplib (Gmail SMTP) – Email integration
-   DuckDuckGo Search (LangChain Community Tool) – Web search capability
-   ZoneInfo (Python stdlib) – Timezone-aware time handling

### 📱 Frontend (Mobile App)

-   Android (Kotlin)
-   LiveKit Android SDK
-   Jetpack Compose
-   Navigation Component
-   ViewModel Architecture

### ☁️ Cloud & Infrastructure

-   LiveKit Cloud – Real-time WebRTC infrastructure
-   Gemini Realtime API – Cloud-hosted LLM
-   Mem0 Cloud / Hosted Memory
-   Gmail SMTP Server
-   wttr.in / Open-Meteo API – Weather data source

### 🔐 Security & Authentication

-   JWT-based LiveKit Token Authentication
-   Environment Variables (.env)
-   App Password-based Gmail Authentication

### 🧠 AI Capabilities

-   Real-time speech-to-text processing
-   Context-aware response generation
-   Tool calling (function execution)
-   Long-term memory retrieval
-   Timezone-aware date & time generation
-   Dynamic tool routing via LLM

------------------------------------------------------------------------

## 🏗 System Architecture

``` mermaid
flowchart LR
    A[Android App] -->|Voice Stream| B[LiveKit Cloud]
    B --> C[Oracle Agent]
    C --> D[Gemini Realtime]
    C --> E[Mem0 Memory]
    C --> F[Tool Layer]

    F --> F1[Time Tool]
    F --> F2[Weather Tool]
    F --> F3[Web Search]
    F --> F4[Email Tool]

    D -->|Response| C
    C -->|Audio Output| B
    B -->|Stream Back| A
```

------------------------------------------------------------------------

## 🔄 Processing Workflow

``` mermaid
sequenceDiagram
    participant U as User
    participant A as Android App
    participant L as LiveKit
    participant O as Oracle Agent
    participant G as Gemini LLM
    participant M as Mem0
    participant T as Tools

    U->>A: Speaks
    A->>L: Stream audio
    L->>O: Deliver audio
    O->>G: Send transcript + context

    alt Personal Question
        O->>M: recall_memory(query)
        M-->>O: Retrieved memory
    end

    alt Real-world Data Required
        O->>T: Execute tool
        T-->>O: Tool output
    end

    G-->>O: Generated response
    O->>L: Stream reply
    L->>A: Deliver audio
    A->>U: Play response
```

------------------------------------------------------------------------

## 🛠️ Intelligent Tool Execution

Oracle dynamically calls tools instead of hallucinating answers and below given are the available tools.

| Tool                   | Description                  |
| ---------------------- | ---------------------------- |
| `get_local_time()`     | Accurate timezone-aware time |
| `get_weather(city)`    | Real-time weather            |
| `search_web(query)`    | DuckDuckGo search            |
| `send_email()`         | Gmail SMTP integration       |
| `recall_memory(query)` | Semantic memory retrieval    |

------------------------------------------------------------------------

## Tool Orchestration Strategy

-   Detect user intent
-   Decide whether tool execution is required
-   Execute tool
-   Inject tool output into LLM context
-   Generate final response

------------------------------------------------------------------------

## 📂 Project Structure

    oracle2.0/
    │
    ├── agent.py                                    # Core AI orchestration engine
    │   ├── Agent initialization                    # Initializes LiveKit Agent + Gemini Realtime model
    │   ├── Memory loading                          # Fetches stored user facts from Mem0 before session starts
    │   ├── Session management                      # Creates AgentSession and connects to LiveKit Cloud
    │   ├── Tool registration                       # Registers callable tools (weather, time, email, search, memory)
    │   └── Shutdown persistence                    # Saves full chat transcript to Mem0 on exit
    │
    ├── tools.py                                    # Executable real-world functions layer
    │   ├── get_local_time()                        # Returns timezone-aware current date & time (no hallucination)
    │   ├── get_weather(city)                       # Fetches real-time weather data from API
    │   ├── search_web(query)                       # Performs live DuckDuckGo web search
    │   ├── send_email(to, subject, message)        # Sends real emails via Gmail SMTP
    │   └── recall_memory(query)                    # Retrieves stored user data from Mem0
    │
    ├── prompts.py                                  # Personality & intelligence rules
    │   ├── AGENT_INSTRUCTION                       # Defines Oracle’s personality and speaking style
    │   ├── SESSION_INSTRUCTION                     # Controls session-level behavior & follow-ups
    │   └── Tool + Memory rules                     # Forces tool usage & memory priority over guessing
    │
    ├── requirements.txt                            # Backend dependency definitions
    │
    ├── .env.example                                # Required environment variables template
    │
    └── Oracle_AI/                                  # Android client application
        └── Android Studio project                  # Mobile app connecting to LiveKit Cloud

------------------------------------------------------------------------
## ⚙️ Environment Configuration
### Create a .env file:

    LIVEKIT_URL=wss://your.livekit.cloud
    LIVEKIT_API_KEY=your_api_key
    LIVEKIT_API_SECRET=your_secret

    GOOGLE_API_KEY=your_gemini_key
    MEM0_API_KEY=your_mem0_key

    GMAIL_USER=yourgmail@gmail.com
    GMAIL_APP_PASSWORD=your_app_password

    USER_ID=your_name
    DEFAULT_CITY=your_location

## 🖥️ Local Development Setup

### 1️⃣ Clone Repository

    git clone https://github.com/YOUR_USERNAME/oracle-2.0.git
    cd oracle-2.0

### 2️⃣ Create Virtual Environment

    python -m venv venv
 
### 3️⃣ Activate Virtual Environment

    powershell -ExecutionPolicy Bypass
    venv\Scripts\activate

### 4️⃣ Install Dependencies

    pip install -r requirements.txt

### 5️⃣ Running the Agent

    python agent.py dev

------------------------------------------------------------------------

## 📱 Android Integration
### The Android client:

-   Uses LiveKit Android SDK
-   Connects to LiveKit room
-   Streams microphone audio
-   Receives voice output
-   Provides mobile UX

### ⚠️ Production Recommendation:
Implement secure backend token generation instead of hardcoded JWT tokens.

------------------------------------------------------------------------

## 🔐 Security Architecture

-   Secrets stored in .env
-   SMTP uses App Password
-   No credentials in Android
-   Use HTTPS in production
-   Token-based authentication for LiveKit
-   Memory isolation via user_id

------------------------------------------------------------------------

## 🌍 Deployment (24/7 Operation)
To run without a laptop:
### Option 1: Railway (Recommended)

-   Push to GitHub
-   Connect Railway
-   Add environment variables
-   Deploy Python service

### Option 2: Render

-   Create Web Service
-   Add environment variables
-   Start command:
        
        python agent.py

### Option 3: Fly.io

-   Deploy Docker container
-   Global low-latency

------------------------------------------------------------------------
## 📊 System Design Considerations
### Why Tool-Augmented LLM?

LLMs hallucinate real-world data.
Tool augmentation ensures:
-   Accurate time
-   Accurate weather
-   Real web results
-   Real email sending

### Why Dual Memory Strategy?

-   Passive injection improves context
-   Active recall ensures reliability
-   Combined → Deterministic memory behavior.

------------------------------------------------------------------------

## 🧪 Testing Checklist
| Test                     | Expected          |
| ------------------------ | ----------------- |
| What time is it?         | Accurate IST time |
| Weather in Chennai?      | Real weather data |
| What is my name?         | Memory recall     |
| Send email               | Email delivered   |
| Repeat personal question | Persistent memory |

------------------------------------------------------------------------

## 🔮 Roadmap

### Phase 1 — Stability
-   Docker support
-   Logging improvements
-   Memory deduplication

### Phase 2 — Feature Expansion
-   Calendar integration
-   Reminder scheduling
-   Task management
-   Note-taking tool

### Phase 3 — Intelligence Upgrade
-   Memory summarization
-   Multi-user isolation
-   Context compression
-   Custom wake-word detection

### Phase 4 — Production Scale
-   Kubernetes deployment
-   Token generation API
-   Rate limiting
-   Analytics dashboard

------------------------------------------------------------------------

## 🔬 Advanced Improvements (Future)

-   RAG-style knowledge retrieval
-   Vector database for memory
-   Streaming TTS voice customization
-   Multi-modal input (camera)
-   Fine-tuned persona models

------------------------------------------------------------------------

## 🎯 Why This Project is Advanced
This project demonstrates:
-   Real-time AI system orchestration
-   LLM + tool integration
-   Persistent semantic memory
-   Mobile-to-cloud architecture
-   Production-level system design thinking

This is not a tutorial chatbot.
This is a complete AI assistant system architecture.

------------------------------------------------------------------------

## 🙏 Acknowledgements

Oracle 2.0 is built using powerful open technologies and platforms:

-   LiveKit – Real-time communication infrastructure
-   Google Gemini Realtime API – Large Language Model engine
-   Mem0 – Persistent long-term memory system
-   Android SDK – Mobile application integration
-   Open-source community contributors who make modern AI development accessible

Special thanks to the AI research and open-source community for advancing real-time multimodal AI systems.

------------------------------------------------------------------------

## 📜 License

MIT License

Copyright (c) 2026 Shaheem B.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

------------------------------------------------------------------------