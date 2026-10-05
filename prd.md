GitHub Trending을 주기적으로 수집해서 Slack으로 보내주는 개인용 자동화 시스템을 구현해줘.

목표는 새로운 시스템을 zero-to-one으로 과하게 만드는 것이 아니라, 기존 오픈소스/라이브러리/표준 기능을 최대한 활용해서 작고 유지보수하기 쉬운 형태로 만드는 것이다.

## 목표

매일 정해진 시간에 자동으로:

1. GitHub Trending 데이터를 가져온다.
2. 관심 있는 repository를 선별한다.
3. 필요한 경우 LLM으로 간단하게 요약한다.
4. Slack의 특정 채널로 digest를 보낸다.
5. 내 컴퓨터가 꺼져 있어도 동작해야 한다.

실행 환경은 별도 서버나 GCP VM이 아니라 **GitHub Actions**를 우선 사용한다.

## 중요한 설계 원칙

- 가능한 한 기존 오픈소스나 검증된 라이브러리를 재사용할 것.
- 이미 잘 구현된 프로젝트를 fork/extend하는 것이 더 낫다면 새로 구현하지 말 것.
- 단순한 문제를 agent framework나 복잡한 infrastructure로 만들지 말 것.
- 서버를 상시 실행하지 말 것.
- GitHub Actions의 cron schedule로 실행할 것.
- API key나 Slack webhook은 코드에 넣지 않고 GitHub Actions Secrets를 사용할 것.
- 가능한 한 적은 파일과 적은 dependency로 유지할 것.
- Docker는 꼭 필요한 경우가 아니면 사용하지 말 것.
- DB도 현재 요구사항에 필요하지 않으면 사용하지 말 것.

## 기존 프로젝트 재사용 검토

구현을 시작하기 전에 다음과 같은 기존 프로젝트/접근법을 검토해줘.

- TrendRadar
- GitHubTrendingRSS
- github-trending-api
- ai-reader 또는 유사한 GitHub Trending digest 프로젝트

현재 요구사항에 가장 적합한 프로젝트가 있다면 그것을 기반으로 최소한의 설정/수정만 하는 방향을 우선 선택해줘.

단, 기존 프로젝트가 지나치게 크거나 유지보수가 어려워서 직접 구현하는 것이 오히려 단순하다면 그 이유를 설명하고 최소 구현으로 진행해줘.

## 초기 버전 기능

첫 버전은 너무 복잡하게 만들지 말고 다음 정도면 충분하다.

### GitHub Trending 수집

기본적으로 daily trending을 수집한다.

가능하다면 아래 정보를 얻는다.

- repository 이름
- URL
- description
- programming language
- total stars
- 오늘 증가한 stars
- owner

GitHub Trending 공식 API가 없다면 안정적인 기존 parser/library 또는 HTML parsing을 사용해도 된다.

### 필터

설정 파일에서 관심 조건을 바꿀 수 있게 한다.

예:

- 관심 언어:
  - Python
  - TypeScript
  - Rust
  - Go

- 관심 키워드:
  - AI
  - LLM
  - agent
  - developer tools
  - infrastructure
  - database

필터가 너무 엄격해서 좋은 repository를 놓치지 않도록 구조를 단순하게 설계한다.

### Slack

Slack Incoming Webhook을 우선 사용한다.

Secret 이름:

SLACK_WEBHOOK_URL

Slack 메시지는 읽기 쉽게 구성한다.

예:

GitHub Trending — 2026-10-05

1. owner/repository
   ⭐ +1,234 today
   Python

   간단한 설명

   https://github.com/...

2. ...

가능하면 Slack Block Kit을 사용해도 되지만, 구현 복잡도가 크게 증가한다면 일반 webhook message로 충분하다.

### LLM 요약

LLM 요약은 optional feature로 구현한다.

환경 변수에 API key가 없으면 원본 description만 사용하고 정상적으로 동작해야 한다.

API key가 있으면 각 repository에 대해 한국어로 1~2문장 정도만 생성한다.

요약 내용:

- 이 프로젝트가 무엇인지
- 왜 개발자가 관심을 가질 만한지

과도한 토큰 사용은 피한다.

가능하면 한 번의 LLM request에 여러 repository를 batch로 넣어서 비용을 줄인다.

Secret 예:

OPENAI_API_KEY

모델명 등은 환경 변수나 config에서 바꿀 수 있도록 한다.

### 중복 방지

매일 같은 repository가 반복될 수 있으므로 가능하면 최근에 보낸 repository는 일정 기간 재전송하지 않도록 한다.

하지만 이를 위해 DB를 도입하지 말 것.

가장 단순하고 GitHub Actions와 잘 맞는 방법을 선택해줘.

예:

- 작은 state JSON
- GitHub Actions cache
- 별도 state branch
- 다른 간단한 방식

각 방식의 trade-off를 보고 가장 유지보수가 쉬운 것을 선택한다.

## GitHub Actions

다음 workflow를 만들어줘.

.github/workflows/digest.yml

요구사항:

- schedule 실행
- workflow_dispatch를 통한 수동 실행 지원
- Ubuntu runner 사용
- dependency 설치
- digest 실행
- Secrets 전달

매일 한국 시간 오전 9시 정도 실행되도록 설정한다.

GitHub Actions schedule timezone 지원 여부를 현재 기준으로 확인해서 가장 명확한 방법을 사용한다.

## 설정

사용자가 코드를 수정하지 않고 config 파일만 수정해서 동작을 바꿀 수 있도록 한다.

예:

config.yaml

다음 항목 정도를 고려한다.

languages:
  - Python
  - TypeScript

keywords:
  - AI
  - LLM
  - agent

max_repositories: 10

use_llm: true

summary_language: ko

중요하지 않은 옵션은 만들지 말 것.

## 프로젝트 크기

직접 구현하는 경우 가능한 한 이런 수준으로 작게 유지해줘.

.
├── main.py
├── trending.py
├── slack.py
├── summarizer.py
├── config.yaml
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── digest.yml

필요하지 않은 파일은 만들지 않아도 된다.

## README

README에는 최소한 아래를 적어줘.

1. 이 프로젝트가 무엇을 하는지
2. Slack Incoming Webhook 만드는 방법
3. GitHub Secret에 SLACK_WEBHOOK_URL 넣는 방법
4. LLM을 사용할 경우 OPENAI_API_KEY 설정 방법
5. config.yaml 수정 방법
6. GitHub Actions 활성화 방법
7. workflow_dispatch로 테스트하는 방법
8. 비용이 발생할 수 있는 부분
9. 로컬에서 테스트하는 방법

처음 사용하는 사람이 10분 안에 설정할 수 있도록 작성한다.

## 작업 방식

바로 코딩부터 하지 말고 먼저 현재 repository를 확인하고 아래를 짧게 정리해줘.

1. 기존 코드 중 재사용할 수 있는 것이 무엇인지
2. 외부 오픈소스를 기반으로 하는 것이 좋은지
3. 직접 최소 구현하는 것이 좋은지
4. 선택한 architecture와 그 이유

그 다음 구현해줘.

구현 후에는 실제로 가능한 범위에서:

- lint 또는 syntax check
- 기본 실행 테스트
- Slack payload 생성 테스트
- GitHub Actions YAML 검토

까지 수행해줘.

최종적으로 아래를 알려줘.

- 추가/수정한 파일
- 필요한 GitHub Secrets
- 내가 직접 해야 하는 설정
- 테스트 방법
- 향후 개선할 만한 기능

가장 중요한 목표는 **기능이 많은 시스템이 아니라, 설정이 쉽고 매일 안정적으로 동작하는 작은 자동화**다.