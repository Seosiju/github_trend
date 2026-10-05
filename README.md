# github_trend

매일 GitHub Trending(daily)을 수집해서 관심 조건으로 필터링하고, 선택적으로 LLM 한국어 요약을 붙여 Slack 채널로 보내는 소형 자동화. 서버 없이 GitHub Actions cron으로 동작한다.

## 동작 방식

1. `gtrending`으로 GitHub Trending 페이지를 스크레이핑 (전체 + `config.yaml`의 관심 언어별)
2. 언어 OR 키워드 매칭으로 필터 → 오늘 증가한 stars 순 정렬 → 상한 적용
3. 최근 `dedup_days`일 내 이미 보낸 repo는 제외 (GitHub Actions cache의 `state.json`)
4. `OPENAI_API_KEY`가 있으면 repo들을 한 번의 요청으로 묶어 1~2문장 요약 생성, 없으면 원문 description 사용
5. Slack Incoming Webhook으로 Block Kit 메시지 전송

## 설정 (10분)

### 1. Slack Incoming Webhook 만들기

1. https://api.slack.com/apps → **Create New App** → **From scratch**
2. **Incoming Webhooks** → **Activate Incoming Webhooks** 켜기
3. **Add New Webhook to Workspace** → 보낼 채널 선택 → Allow
4. `https://hooks.slack.com/services/...` URL 복사

### 2. GitHub Secrets 등록

Repo → **Settings → Secrets and variables → Actions → New repository secret**

| Name | 값 | 필수 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | 위 webhook URL | O |
| `OPENAI_API_KEY` | OpenAI API 키 | X (없으면 요약 없이 description만 전송) |

CLI로 등록할 수도 있다:

```sh
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/..."
gh secret set OPENAI_API_KEY --body "sk-..."
```

### 3. config.yaml 수정

`languages`, `keywords`, `period`(daily/weekly/monthly), `max_repositories`, `use_llm`, `summary_language`, `llm_model`, `dedup_days`를 조정한다. 언어는 `github.com/trending/<slug>`의 slug 기준(대소문자 무관, 예: `Python`, `C++`은 `cpp`).

### 4. GitHub Actions 활성화 / 테스트

- 스케줄: 매일 **09:00 KST** (cron `0 0 * * *`, UTC 기준)
- 수동 테스트: **Actions → digest → Run workflow**
- GitHub 스케줄 잡은 부하가 몰리면 수 분 지연될 수 있다. 공짜 cron의 통상 특성이다.
- `keepalive` workflow가 매월 1일 빈 커밋을 push해 60일 무활동 시 스케줄이 꺼지는 것을 방지한다.

## 로컬 테스트

```sh
pip install -r requirements.txt
python main.py --dry-run   # Slack 전송 없이 payload 확인
SLACK_WEBHOOK_URL=... python main.py   # 실제 전송 테스트
```

`state.json`에 발송 이력이 생긴다(gitignore 대상). 초기화하려면 파일을 지우면 된다.

## 비용

- GitHub Actions public repo: 무료 (private repo면 월 무료분 안에서 수 분 소모)
- Slack Incoming Webhook: 무료
- OpenAI: 기본 `gpt-5-mini`, 하루 수십 repo 요약 기준 월 수 센트 수준. `use_llm: false` 또는 키 미등록 시 0원

## 구조

```
main.py         수집→dedup→요약→전송 오케스트레이션, state.json 관리
trending.py     gtrending 래핑 + 언어/키워드 필터
slack.py        Block Kit payload 생성 + webhook 전송
summarizer.py   OpenAI 배치 요약 (키 없으면 graceful skip)
config.yaml     사용자 설정
.github/workflows/digest.yml   매일 09:00 KST cron + 수동 실행
```
