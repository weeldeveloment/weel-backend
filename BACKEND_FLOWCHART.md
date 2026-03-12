# Weel Backend Architecture Flowchart

## System Overview

```mermaid
flowchart TB
    subgraph Clients["Client Applications"]
        Mobile["Mobile App (Expo)"]
        Web["Web App (Next.js)"]
        Admin["Admin Panel"]
        Telegram["Telegram Bot"]
    end

    subgraph Gateway["API Gateway Layer"]
        Nginx["Nginx / Load Balancer"]
    end

    subgraph Backend["Django Backend (ASGI)"]
        ASGI["Daphne ASGI Server"]
        
        subgraph Middleware["Middleware Layer"]
            CORS["CORS Headers"]
            Auth["JWT Authentication"]
            Logging["Request Logging"]
            Prometheus["Prometheus Metrics"]
        end
        
        subgraph API["REST API Endpoints"]
            Users["Users API"]
            Property["Property API"]
            Booking["Booking API"]
            Chat["Chat WebSocket"]
            Payment["Payment API"]
            Notification["Notification API"]
            Stories["Stories API"]
            Sanatorium["Sanatorium API"]
        end
    end

    subgraph Async["Async Task Processing"]
        Celery["Celery Workers"]
        Beat["Celery Beat Scheduler"]
    end

    subgraph Storage["Data Storage"]
        PostgreSQL["PostgreSQL Database"]
        Redis["Redis Cache"]
        MinIO["MinIO Object Storage"]
    end

    subgraph External["External Services"]
        Eskiz["Eskiz SMS/Email"]
        Firebase["Firebase (Push Notifications)"]
        Plum["Plum Payments"]
        ExchangeAPI["Currency Exchange API"]
    end

    Clients --> Nginx
    Nginx --> ASGI
    ASGI --> Middleware
    Middleware --> API
    
    API --> PostgreSQL
    API --> Redis
    API --> MinIO
    
    API --> Celery
    Beat --> Celery
    
    Celery --> PostgreSQL
    Celery --> Redis
    Celery --> External
    
    API --> External
```

## API Endpoint Architecture

```mermaid
flowchart LR
    subgraph UserEndpoints["User Authentication & Profile"]
        U1["Client Register/Login"]
        U2["Partner Register/Login"]
        U3["OTP Verification"]
        U4["Profile Management"]
        U5["Token Refresh"]
        U6["Card Management"]
    end

    subgraph PropertyEndpoints["Property Management"]
        P1["Property CRUD"]
        P2["Search & Filter"]
        P3["Image Upload"]
        P4["Amenities"]
        P5["Reviews"]
    end

    subgraph BookingEndpoints["Booking System"]
        B1["Create Booking"]
        B2["Calendar Management"]
        B3["Block Dates"]
        B4["Hold Dates"]
        B5["Cancel Booking"]
        B6["Accept/Reject"]
    end

    subgraph ChatEndpoints["Real-time Chat"]
        C1["WebSocket Connection"]
        C2["Send Message"]
        C3["Receive Message"]
        C4["Chat History"]
    end

    subgraph PaymentEndpoints["Payments"]
        PA1["Payment Intent"]
        PA2["Payment Callback"]
        PA3["Refund"]
        PA4["Exchange Rates"]
    end

    subgraph NotificationEndpoints["Notifications"]
        N1["Push Notifications"]
        N2["Booking Reminders"]
        N3["Payment Reminders"]
        N4["In-App Notifications"]
    end
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB
    participant Redis
    participant Eskiz

    Client->>API: POST /api/user/client/register/
    API->>DB: Check phone exists
    API->>Eskiz: Send OTP SMS
    API->>Redis: Store OTP (5 min TTL)
    API-->>Client: OTP Sent

    Client->>API: POST /api/user/client/register/verify/
    API->>Redis: Verify OTP
    Redis-->>API: Valid OTP
    API->>DB: Create Client
    API->>API: Generate JWT (Access + Refresh)
    API-->>Client: JWT Tokens

    Client->>API: API Request + Access Token
    API->>API: Validate JWT
    API-->>Client: Response

    Client->>API: POST /api/user/refresh/
    API->>API: Validate Refresh Token
    API->>API: Rotate Tokens
    API-->>Client: New JWT Tokens
```

## Booking Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB
    participant Celery
    participant Notification
    participant Partner

    Client->>API: GET /api/booking/properties/:id/calendar/
    API->>DB: Query available dates
    DB-->>API: Calendar dates
    API-->>Client: Available dates

    Client->>API: POST /api/booking/client/
    API->>DB: Create booking (pending payment)
    API->>DB: Hold calendar dates
    API-->>Client: Booking created

    Client->>API: Process Payment
    API->>DB: Update booking status

    Celery->>Notification: Send booking notification
    Notification->>Partner: Push notification
    Notification->>Client: Booking confirmation

    Partner->>API: POST /api/booking/partner/:id/accept/
    API->>DB: Update booking status (confirmed)
    API-->>Client: Booking confirmed
```

## WebSocket Chat Flow

```mermaid
flowchart TB
    Client1["Client 1"]
    Client2["Client 2"]
    
    subgraph WebSocket["Django Channels"]
        WSServer["ChatConsumer"]
        subgraph Channel["Channel Layer"]
            RedisChannel["Redis Channel"]
        end
    end
    
    subgraph Backend2["Backend"]
        DB[(Database)]
    end
    
    Client1 -- "ws://chat/" --> WSServer
    Client2 -- "ws://chat/" --> WSServer
    WSServer -- "Store/Read" --> DB
    WSServer <-> RedisChannel
```

## Celery Task Architecture

```mermaid
flowchart TB
    subgraph Scheduled["Celery Beat (Scheduled Tasks)"]
        S1["persist_story_views<br/>Every 10 min"]
        S2["update_exchange_rate<br/>Every 24 hours"]
        S3["send_booking_reminders<br/>Every 10 hours"]
        S4["send_pending_booking_payment_reminders<br/>Every 5 min"]
    end

    subgraph OnDemand["On-Demand Tasks"]
        O1["Push Notifications"]
        O2["SMS Sending"]
        O3["Image Compression"]
        O4["Video Compression"]
        O5["Email Sending"]
    end

    subgraph Workers["Celery Workers"]
        W1["Worker 1"]
        W2["Worker 2"]
        W3["Worker N"]
    end

    subgraph Queues["Redis Broker"]
        Q1["Default Queue"]
        Q2["High Priority"]
        Q3["Low Priority"]
    end

    Scheduled --> Queues
    OnDemand --> Queues
    Queues --> Workers
    Workers --> ExternalServices["External Services"]
```

## Database Schema Overview

```mermaid
erDiagram
    Client {
        uuid guid PK
        string phone_number
        string full_name
        datetime created_at
    }
    
    Partner {
        uuid guid PK
        string phone_number
        string full_name
        boolean is_verified
        datetime created_at
    }
    
    Property {
        uuid guid PK
        uuid partner_id FK
        string title
        string address
        decimal price
        integer guest_count
        string status
    }
    
    Booking {
        uuid guid PK
        uuid client_id FK
        uuid property_id FK
        date check_in
        date check_out
        string status
        decimal total_price
    }
    
    CalendarDate {
        uuid guid PK
        uuid property_id FK
        date date
        boolean is_blocked
        boolean is_held
        integer price
    }
    
    Message {
        uuid guid PK
        uuid sender_id FK
        uuid receiver_id FK
        text content
        datetime created_at
    }
    
    Notification {
        uuid guid PK
        uuid user_id FK
        string title
        string body
        boolean is_read
    }
    
    Payment {
        uuid guid PK
        uuid booking_id FK
        decimal amount
        string currency
        string status
        string payment_method
    }
    
    Client ||--o{ Booking : "makes"
    Partner ||--o{ Property : "owns"
    Property ||--o{ Booking : "has"
    Property ||--o{ CalendarDate : "has"
    Booking ||--|| Payment : "has"
    Client ||--o{ Message : "sends"
    Partner ||--o{ Message : "sends"
    Client ||--o{ Notification : "receives"
    Partner ||--o{ Notification : "receives"
```

## Technology Stack

```
┌─────────────────────────────────────────────────────┐
│                    Frontend Apps                     │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │   Expo   │  │ Next.js  │  │   Admin Panel   │   │
│  │  Mobile  │  │    Web   │  │  (Django Unfold)│   │
│  └──────────┘  └──────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                  API Layer                           │
│  ┌─────────────────────────────────────────────┐    │
│  │  Django REST Framework + Django Channels    │    │
│  │  - JWT Authentication (SimpleJWT)           │    │
│  │  - CORS Headers                            │    │
│  │  - Rate Limiting                           │    │
│  │  - Request Logging                         │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              Background Tasks                        │
│  ┌─────────────────────────────────────────────┐    │
│  │           Celery + Celery Beat              │    │
│  │  - SMS Notifications                        │    │
│  │  - Push Notifications (Firebase)            │    │
│  │  - Image/Video Compression                  │    │
│  │  - Scheduled Tasks                          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│               Data Storage                           │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │PostgreSQL│  │  Redis   │  │  MinIO (S3)     │   │
│  │Database  │  │  Cache   │  │  Media Storage  │   │
│  └──────────┘  └──────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              External Services                       │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │  Eskiz   │  │ Firebase │  │   Plum Payment  │   │
│  │ SMS/Email│  │  FCM     │  │   Gateway       │   │
│  └──────────┘  └──────────┘  └─────────────────┘   │
│  ┌──────────┐                                      │
│  │ Exchange │                                      │
│  │ Rate API │                                      │
│  └──────────┘                                      │
└─────────────────────────────────────────────────────┘
```

## Request Flow (Detailed)

```mermaid
flowchart LR
    A[HTTP Request] --> B{HTTPS?}
    B -->|No| C[Redirect HTTPS]
    B -->|Yes| D[Nginx]
    D --> E[Daphne ASGI]
    E --> F{Path Type?}
    F -->|WebSocket| G[Channels Router]
    F -->|HTTP| H[Django Middleware]
    
    H --> I[Prometheus Metrics]
    I --> J[CORS Check]
    J --> K[Authentication]
    K --> L{Authenticated?}
    L -->|No| M[401 Unauthorized]
    L -->|Yes| N[URL Router]
    N --> O[View/ViewSet]
    O --> P[Serializer]
    P --> Q[Model/DB Query]
    Q --> R[Database]
    R --> Q
    Q --> S[Response]
    S --> T[Response Middleware]
    T --> U[Client]
    
    G --> V[WebSocket Consumer]
    V --> W[Channel Layer Redis]
    W --> X[Broadcast Message]
    X --> Y[Connected Clients]
```

## Key Backend Apps

| App | Purpose | Key Features |
|-----|---------|--------------|
| `users` | Authentication & Profiles | JWT auth, OTP verification, Client/Partner management |
| `property` | Property Management | CRUD, Search, Filters, Image handling |
| `booking` | Booking System | Calendar, Reservations, Status management |
| `chat` | Real-time Messaging | WebSocket, Message history, Typing indicators |
| `payment` | Payment Processing | Payment intents, Refunds, Currency exchange |
| `notification` | Notifications | Push notifications, Reminders, In-app alerts |
| `stories` | Stories Feature | View tracking, Media management |
| `sanatorium` | Sanatorium Services | Specialized booking features |
| `bot` | Telegram Integration | Bot commands, Webhook handling |
| `admin_auth` | Admin Authentication | Admin panel access control |

## Deployment Architecture

```mermaid
flowchart TB
    subgraph Internet["Internet"]
        Users["Users"]
    end

    subgraph CDN["CDN Layer"]
        Cloudflare["Cloudflare"]
    end

    subgraph LoadBalancer["Load Balancer"]
        Nginx["Nginx"]
    end

    subgraph Application["Application Servers"]
        App1["Django App 1"]
        App2["Django App 2"]
        App3["Django App N"]
    end

    subgraph WebSocket["WebSocket Servers"]
        WS1["Daphne 1"]
        WS2["Daphne 2"]
    end

    subgraph Background["Background Workers"]
        Celery1["Celery Worker 1"]
        Celery2["Celery Worker 2"]
        Beat["Celery Beat"]
    end

    subgraph Data["Data Layer"]
        DB[(PostgreSQL)]
        Redis[(Redis)]
        MinIO[(MinIO)]
    end

    Users --> Cloudflare
    Cloudflare --> Nginx
    Nginx --> App1
    Nginx --> App2
    Nginx --> App3
    Nginx --> WS1
    Nginx --> WS2
    
    App1 --> DB
    App2 --> DB
    App3 --> DB
    
    App1 --> Redis
    App2 --> Redis
    App3 --> Redis
    
    Celery1 --> DB
    Celery2 --> DB
    Celery1 --> Redis
    Celery2 --> Redis
    
    Beat --> Celery1
    Beat --> Celery2
```

## Monitoring & Observability

```
┌─────────────────────────────────────┐
│         Monitoring Stack            │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │Prometheus│  │  Django Metrics │  │
│  │ Metrics  │  │  - Request time │  │
│  │          │  │  - DB queries   │  │
│  │          │  │  - Cache hits   │  │
│  └─────────┘  └─────────────────┘  │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │   Logs  │  │  - File logs    │  │
│  │          │  │  - JSON format  │  │
│  │          │  │  - Rotation     │  │
│  └─────────┘  └─────────────────┘  │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │  Health │  │  - DB check     │  │
│  │  Checks │  │  - Redis check  │  │
│  │          │  │  - API status   │  │
│  └─────────┘  └─────────────────┘  │
└─────────────────────────────────────┘
```

## Security Layers

```
┌────────────────────────────────────────┐
│           Security Measures            │
│                                        │
│  1. HTTPS/TLS Encryption              │
│  2. JWT Token Authentication           │
│  3. CORS Configuration                 │
│  4. Rate Limiting (5-60 req/min)      │
│  5. CSRF Protection                    │
│  6. SQL Injection Prevention (ORM)    │
│  7. XSS Protection                     │
│  8. HSTS Headers                       │
│  9. Secure Cookie Flags                │
│ 10. Input Validation (Serializers)    │
│ 11. Password Hashing (if applicable)  │
│ 12. OTP Verification                   │
└────────────────────────────────────────┘
```
