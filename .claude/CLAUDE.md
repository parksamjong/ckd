# Claude Code 글로벌 가이드라인 & 스킬 레지스트리

---

## 0. 멀티에이전트 자동 오케스트레이션 (항상 적용)

**별도 명령 없이** 아래 조건에 해당하면 자동으로 orchestrator 패턴을 사용한다.

### 자동 활성화 조건
- 프론트엔드 + 백엔드를 **동시에** 수정해야 하는 작업
- **3개 이상**의 독립적으로 실행 가능한 서브태스크가 있는 작업
- 예상 작업 시간이 **30분 이상**인 복잡한 기능 구현
- "전체", "모두", "리뉴얼", "추가해줘 (여러 항목)" 등의 키워드 포함

### 자동 실행 절차 (명령어 불필요)
1. **칸반보드 생성** — 서브태스크마다 `TaskCreate` 호출, 보드에서 전체 진행 추적
2. **병렬 디스패치** — 독립 태스크는 단일 메시지에서 `Agent` 동시 호출 (`isolation: worktree`)
3. **모니터링** — `TaskGet`으로 각 에이전트 상태 확인
4. **통합** — 완료 후 결과 병합, 빌드/테스트 검증

### 에이전트 역할 분담
| 에이전트 | 담당 | 정의 파일 |
|---|---|---|
| orchestrator | 전체 지휘·통합 | `.claude/agents/orchestrator.md` |
| backend-agent | API·서비스·DB | `.claude/agents/backend-agent.md` |
| frontend-agent | UI·컴포넌트·라우터 | `.claude/agents/frontend-agent.md` |
| test-agent | 테스트 작성·실행 | `.claude/agents/test-agent.md` |
| code-reviewer | 리뷰·보안 점검 | `.claude/agents/code-reviewer.md` |

---

## 1. Karpathy 코딩 원칙 (andrej-karpathy-skills)

> 출처: https://github.com/multica-ai/andrej-karpathy-skills

### 코딩 전에 생각하기
- 가정을 명시적으로 표현하고, 불확실하면 질문
- 여러 해석이 있으면 모두 제시하고 조용히 선택하지 않기
- 더 간단한 방법이 있으면 먼저 언급
- 혼란스러운 부분이 있으면 멈추고 이름 붙이기

### 단순성 우선
- 최소 코드로 문제 해결. 추측성 기능 없음
- 요청 범위 밖의 기능 추가 금지
- 단일 용도 코드에 추상화 금지
- 불가능한 시나리오에 대한 오류 처리 금지

### 수술적 변경
기존 코드 편집 시 필요한 부분만 수정하고, 현존 스타일 유지. 자신의 변경으로 인해 불필요해진 항목만 제거.

### 목표 중심 실행
작업을 검증 가능한 목표로 변환하고, 각 단계마다 확인. 다단계 작업은 간단한 계획 수립.

### 한국어 마침표 규칙
한국어로 출력할 때 문장 끝에 콜론(`:`)을 쓰지 말 것. 마침표(`.`), 물음표(`?`), 느낌표(`!`)만 사용.

### 한국어 파일 헤더
새 소스 파일 첫 줄에 역할을 설명하는 한국어 주석 추가. 예: `// 사용자 인증 상태를 관리하는 Context Provider`

### 계획 + 체크리스트 + 컨텍스트 노트
비자명한 작업 전에 세 가지 산출물(plan, checklist, context-notes) 준비 후 시작.

### 완료 전 테스트 실행
코드 변경 후 반드시 테스트 실행 후 결과 보고. 테스트 없으면 최소한 빌드 확인.

### 의미론적 커밋
한 문장으로 설명 가능한 논리적 변경 단위로 커밋. 여러 개념을 섞지 말 것.

### 에러 직접 읽기
에러 메시지와 스택 트레이스를 정확히 읽고, 추측 기반 수정 대신 실제 원인 파악 후 대응.

---

## 2. Superpowers 스킬 세트 (obra/superpowers)

> 출처: https://github.com/obra/superpowers

### 테스팅
- `/test-driven-development` — 테스트 먼저 작성 후 구현

### 디버깅
- `/systematic-debugging` — 가설 수립 → 검증 → 범위 축소 순서로 디버깅
- `/verification-before-completion` — 완료 전 반드시 실제 동작 검증

### 계획 & 실행
- `/brainstorming` — 열린 탐색으로 솔루션 탐구
- `/writing-plans` — 구조화된 실행 계획 수립
- `/executing-plans` — 계획 단계별 실행 및 진행 추적

### 협업
- `/dispatching-parallel-agents` — 독립 태스크를 병렬 에이전트로 분배
- `/requesting-code-review` — 코드 리뷰 요청 형식화
- `/receiving-code-review` — 리뷰 피드백 체계적 처리
- `/using-git-worktrees` — 격리된 worktree로 병렬 작업
- `/finishing-a-development-branch` — 브랜치 정리 및 PR 준비
- `/subagent-driven-development` — 서브에이전트 기반 개발 분업

### 메타
- `/writing-skills` — 새 스킬 정의 작성
- `/using-superpowers` — superpowers 활용 가이드

---

## 3. Understand-Anything 코드 이해 스킬 (Egonex-AI)

> 출처: https://github.com/Egonex-AI/Understand-Anything

- `/understand` — 코드베이스 전체 분석 → 인터랙티브 대시보드 생성
- `/understand-chat` — 코드베이스에 대한 자연어 Q&A
- `/understand-diff` — 변경 사항(diff) 상세 분석
- `/understand-explain` — 특정 함수/모듈 심층 설명

**기술 스택:** TypeScript + React Flow + tree-sitter (WASM) + Zustand

---

## 4. claude-video 영상 분석 스킬 (bradautomates)

> 출처: https://github.com/bradautomates/claude-video

- `/watch <URL|파일>` — 영상 분석 (YouTube URL 또는 로컬 파일)

**동작 방식:**
1. `yt-dlp`로 캡션 먼저 추출 (없으면 Whisper API로 자막 생성)
2. `ffmpeg`로 키프레임 추출 (scene-aware)
3. 중복 프레임 제거 후 Claude에 전달

**세부도 모드:**
- `--detail efficient` — 빠른 요약
- `--detail balanced` — 균형 (기본값)
- `--detail token-burner` — 전체 프레임 커버

---

## 5. agentmemory 지속 메모리 스킬 (rohitg00)

> 출처: https://github.com/rohitg00/agentmemory

**설치:** `npx skills add rohitg00/agentmemory -y`

**핵심 기능:**
- 4단계 메모리 계층: 작업(Working) / 에피소드(Episodic) / 의미(Semantic) / 절차(Procedural)
- 검색: BM25 + 벡터 + 지식 그래프 하이브리드 (R@5 95.2%)
- 53개 MCP 도구 (메모리 저장, 검색, 세션 관리)
- 실시간 메모리 뷰어: `http://localhost:3113`
- 12개 자동 캡처 훅으로 도구 사용 자동 기록
- 다중 에이전트 간 메모리 공유 (MCP + REST)
- 연간 비용 ~$10 (170K 토큰)

---

## 6. Remotion 비디오 생성 스킬 (wshuyi)

> 출처: https://github.com/wshuyi/remotion-video-skill

- `/remotion <설명>` — Remotion 프레임워크로 프로그래매틱 비디오 생성
- React + TypeScript 기반 영상 컴포넌트 자동 생성
- 애니메이션, 자막, 장면 전환 포함 단편 영상 제작

---

## 7. Skill Creator 에이전트 스킬 제작 (FrancyJGLisboa)

> 출처: https://github.com/FrancyJGLisboa/agent-skill-creator

- 기존 워크플로우를 재사용 가능한 AI 에이전트 스킬로 변환
- 17개 플랫폼 (Claude Code, Cursor, Codex 등) 동시 배포 지원
- 스킬 템플릿 자동 생성, 테스트, 최적화

---

## 8. Korean Skills — 한국어 AI 글쓰기 교정 (DaleSeo)

> 출처: https://github.com/DaleSeo/korean-skills

**설치:**
```
npx skills add daleseo/korean-skills
# 또는 특정 스킬만:
npx skills add daleseo/korean-skills@humanizer
```

### `/humanizer` — AI 한국어 패턴 감지 및 교정

KatFishNet 논문(ArXiv 2503.00032v4) 기반, 실증적 언어학 분석 (쉼표 패턴 94.88% AUC).

**분석하는 40가지 패턴 (S1/S2/S3 심각도):**
- **S1 (고위험):** 쉼표 과다 사용, 번역투 (`에 대해`, `통해`, `되어진다`), AI 어휘 과용
- **S2 (중위험):** 띄어쓰기 경직성, 품사 다양성 부족, 대명사 과다
- **S3 (저위험):** 복수형 과다, 구조적 단조로움

**사용 시점:** ChatGPT/Claude/Gemini 생성 한국어 텍스트를 자연스럽게 만들 때.

### `/grammar-checker` — 한국어 문법·맞춤법·띄어쓰기·구두점 검사

### `/style-guide` — 한국어 문서 스타일 일관성 점검

---

## 9. oh-my-claudecode 다중 에이전트 오케스트레이션 (Yeachan-Heo)

> 출처: https://github.com/Yeachan-Heo/oh-my-claudecode

**설치:** `setup omc` 또는 `/oh-my-claudecode:omc-setup`

### 핵심 원칙
- 특화된 작업을 적절한 에이전트에 위임
- "증거 우선": 결론 전에 결과 검증 후 진행
- 품질 유지하며 최소 경로 선택
- 공식 문서 우선 참조

### 주요 슬래시 커맨드

| 커맨드 | 설명 |
|---|---|
| `/team` | 팀 오케스트레이션 (team-plan → team-prd → team-exec → team-verify → team-fix) |
| `/autopilot` | 자율 실행 모드 |
| `/ralph` | 검증/수정 루프가 있는 지속 모드 |
| `/deep-interview` | 소크라테스식 요구사항 명확화 |
| `/ask` | 멀티 프로바이더 어드바이저 |

### 20개+ 전문 에이전트 카탈로그
`explore` · `analyst` · `planner` · `architect` · `debugger` · `executor` · `verifier` · `code-reviewer` · `test-engineer` · `security-reviewer` 등

### 모델 라우팅 전략
- **Haiku**: 빠른 조회, 단순 작업
- **Sonnet**: 표준 개발 작업
- **Opus**: 복잡한 분석, 아키텍처 설계

### 실행 프로토콜
- 광범위 요청 → 먼저 탐색 후 계획 수립
- "저자 작성"과 "검토"를 반드시 별도 단계로 분리
- 완료 조건: 미완료 작업 0개 + 테스트 통과 + 검증 증거 수집
- 커스텀 스킬: `.omc/skills/` 또는 `~/.omc/skills/`에서 관리

---

## 10. Fable 5 제품광고영상 자동완성 워크플로우

> 출처: https://challenzonedu.notion.site/Fable-5-3979d76136ea80c8b1ebf30df8504352
> 스킬 다운로드: Google Drive (Fable5로 만든 제품광고스튜디오 클로드 스킬)

**모델:** Claude Fable 5 (`claude-fable-5`)

### 실습1. 광고 스튜디오 개발
```
[Prompt]
제품명, 소구점, 광고 포맷, 무드를 입력하면 자동으로 광고 제작안을 생성하는
React Artifact를 만들어줘.

기능 구성:
- 씬별 스토리보드 생성 (스토리가 연결되도록)
- 광고 포맷별 최적화 (15초/30초/1분)
- 무드보드 시각화
```

**핵심 활용 패턴:**
- 제품명 + 소구점 + 포맷 + 무드 → React Artifact 자동 생성
- Fable 5의 멀티모달 + 장문 컨텍스트 활용
- 광고 스크립트 → 씬별 스토리보드 자동 분기

### `/ad-studio` 스킬 (설치 완료)

> 설치 경로: `~/.claude/skills/ad-studio/`
> 스킬 파일: Google Drive (Fable5로 만든 제품광고스튜디오 클로드 스킬)

**트리거**: "광고 제작안 만들어줘", "AD STUDIO 열어줘", "씬별 광고 프롬프트", "멀티샷 광고 프롬프트", 제품명 + 광고/스토리보드/씬/이미지 프롬프트/영상 프롬프트/부유샷/숏폼/TV CF 조합

**지원 포맷**:
- `float` — 프리미엄 부유샷 (럭셔리 매크로)
- `shortform` — 숏폼 광고 (릴스/틱톡)
- `tvcf` — TV CF (시네마틱)

**핵심 기능**: 씬별 스토리보드 + 자막 카피 + 이미지/영상 프롬프트(한글·영문) + 멀티샷 프롬프트 + 제품 이미지 분석 → 노텍스트 규칙 자동 적용

---

## 11. Ouroboros — 자기 참조적 AI 하네스 & 에이전트 OS (Q00)

> 출처: https://github.com/Q00 / https://wpti.dev
> 설치 경로: `~/.claude/skills/ouroboros/` (로컬 설치 완료)

**"Stop prompting. Start specifying"** — 비결정적 에이전트 작업을 재현 가능하고 관찰 가능한 실행 계약으로 변환하는 자기 참조적 AI 하네스.

### 핵심 워크플로우

```
Interview → Seed → Execute → Evaluate → Evolve (수렴까지 반복)
```

- 모호성 ≤ 0.2 → Seed 생성
- 온톨로지 유사도 ≥ 0.95 → 수렴 종료

### 주요 명령어

| 명령어 | 설명 |
|---|---|
| `py -3.12 -m ouroboros setup` | 런타임 등록 및 프로젝트 설정 |
| `py -3.12 -m ouroboros init "태스크"` | 소크라테스식 인터뷰로 숨겨진 가정 노출 |
| `py -3.12 -m ouroboros auto` | 전체 파이프라인 자동 실행 |
| `py -3.12 -m ouroboros run` | Double Diamond 분해로 실행 |
| `py -3.12 -m ouroboros qa` | 아티팩트 QA 검증 |
| `py -3.12 -m ouroboros tui` | 인터랙티브 TUI 모니터 |
| `py -3.12 -m ouroboros pm` | PRD(제품 요구사항 문서) 생성 |
| `py -3.12 -m ouroboros status` | 세션 상태 확인 |

### 아키텍처 (3계층)

```
Shell (ourocode)         — 터미널 UI
Apps (ouroboros-plugins) — 도메인 워크플로우
OS (ouroboros)           — Seed · Ledger · Runtime · MCP 코어
```

- **PAL Router**: 비용 최적화 모델 라우팅
- **Double Diamond**: 설계-분해 패턴
- **Event Sourcing**: 실행 이력 지속성

### 지원 런타임

Claude Code · Codex CLI · GitHub Copilot CLI · OpenCode · Hermes · Gemini · Kiro CLI

### 관련 논문 (하네스 엔지니어링)

| 논문 | 핵심 내용 |
|---|---|
| Externalization in LLM Agents (2026.04) | Memory·Skill·Protocol·Harness 4축 외부화 프레임워크 |
| Agentic Harness Engineering (2026.04) | 폐쇄 루프 자동 진화, Terminal-Bench 2에서 69.7%→77.0% |
| AI Harness Engineering (2026.05) | 하네스 11개 책임 컴포넌트, H0-H3 4단계 진행 모델 |
| Meta-Harness (2026.03) | 하네스 코드 자동 탐색·최적화, SOTA 초과 달성 |

---

## 12. Agent Reach — AI 에이전트 인터넷 접근 능력 레이어 (Panniantong)

> 출처: https://github.com/Panniantong/Agent-Reach
> ⭐ 53k stars

AI 에이전트에게 인터넷 읽기/검색 능력을 한 번에 부여하는 **능력 레이어(capability layer)**.
Twitter, Reddit, YouTube, GitHub, Bilibili, 小红书, RSS, 일반 웹페이지를 API 비용 없이 접근 가능.

### 설치

에이전트에게 한 문장 전달:
```
帮我安装 Agent Reach：https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md
```

안전 모드 (시스템 패키지 자동 설치 없이 안내만):
```
帮我安装 Agent Reach（安全模式）：... --safe
```

업데이트:
```
帮我更新 Agent Reach：https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/update.md
```

### 주요 능력

| 명령 예시 | 내부 도구 |
|---|---|
| "이 링크 내용 봐줘" | `curl https://r.jina.ai/URL` |
| "이 GitHub 레포 설명해줘" | `gh repo view owner/repo` |
| "이 YouTube 영상 요약해줘" | `yt-dlp` 자막 추출 |
| "Bilibili에서 AI 튜토리얼 찾아줘" | `bili search` (로그인 불필요) |
| "LLM 프레임워크 비교 검색해줘" | Exa 시맨틱 검색 |
| "이 RSS 구독해줘" | `feedparser` |

### 설계 철학
- 도구가 아닌 **능력 레이어** — 선정·설치·진단·라우팅만 담당, 실제 읽기는 상위 도구가 직접 호출
- SKILL.md를 읽은 에이전트가 상황에 맞는 도구를 자율 선택
- 로그인 필요 플랫폼(小红书, Twitter, Reddit 등)은 `帮我配 XXX`로 개별 설정

---

## 13. Agent Reachout — Claude Code → Telegram 알림 및 Human-in-the-Loop (vibe-with-me-tools)

> 출처: https://github.com/vibe-with-me-tools/agent-reachout

Claude Code 작업이 끝나거나 결정이 필요할 때 **Telegram으로 직접 알림**을 보내는 Claude Code 플러그인.
에이전트가 사용자에게 찾아오는 인터럽트 드리븐 워크플로우 구현.

### 흐름

```
Claude Code → Agent Reachout → Telegram → 사용자 답장 → 에이전트 재개
```

### 주요 기능

- 작업 완료 / 블로커 도달 / 결정 필요 시 Telegram 알림 발송
- 단방향 알림 + 양방향 대화 모두 지원
- 에이전트 **pause → 질문 → resume** 패턴
- Telegram에서 `/task` 명령으로 Claude Code 태스크 원격 시작

### 설치

**사전 조건:** Claude Code CLI, Bun, Telegram 계정

1. [@BotFather](https://t.me/botfather)에서 봇 토큰 발급
2. [@userinfobot](https://t.me/userinfobot)에서 본인 Chat ID 확인
3. 환경변수 설정 (`~/.claude/settings.json` 또는 쉘 프로파일):
   ```json
   { "env": { "AGENT_REACHOUT_TELEGRAM_BOT_TOKEN": "...", "AGENT_REACHOUT_TELEGRAM_CHAT_ID": "..." } }
   ```
4. Claude Code에서 플러그인 설치:
   ```
   /plugin marketplace add vibe-with-me-tools/agent-reachout
   /plugin install agent-reachout@agent-reachout
   ```

### Telegram 명령어

| 명령 | 설명 |
|---|---|
| `/task <설명>` | 새 작업 시작 (큐잉) |
| `/continue <설명>` | 최근 세션 이어서 |
| `/resume <id> <설명>` | 특정 세션 재개 |
| `/history` | 최근 작업 목록 |
| `/status` | 현재 작업 + 큐 상태 |
| `/cancel` | 현재 작업 취소 및 큐 비우기 |

### 환경변수 주요 설정

- `AGENT_REACHOUT_NOTIFY_DEFAULT_TIMEOUT_MS` — 응답 대기 시간 (기본: 300000ms / 5분)
- `AGENT_REACHOUT_ALLOWED_TOOLS` — 허용 도구 목록 (`--allowedTools` 전달)

---

## 14. BrowserAct — AI 웹 스크래핑 & 브라우저 자동화 플랫폼 (browser-act)

> 출처: https://github.com/browser-act/browseract-api-examples
> 공식 사이트: https://www.browseract.com/

**"Any Site, No Code, Zero Limits, Reliable Data"** — AI 기반 웹 스크래핑·자동화 클라우드 플랫폼.
Agent-Reach에서 "로그인 후 웹 조작, 폼 제출 등 '직접 손대는(手动)' 장면"에 추천하는 도구.

### 핵심 기능

- **AI-Workflow**: 사전 정의 템플릿 + 커스텀 워크플로우 + 배치 처리
- **Predefined Templates**: 공식 제공 워크플로우로 코드 없이 즉시 실행
- **REST API**: Python / Java / Node.js 모두 지원
- 30+ 플랫폼 스크래핑 스킬, Claude Code / Cursor 등 AI 에이전트 연동 가능

### 주요 API 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `POST /v2/workflow/run-task` | 커스텀 워크플로우 태스크 시작 |
| `POST /v2/workflow/run-task-by-template` | 공식 템플릿으로 태스크 시작 |
| `GET /v2/workflow/get-task-status` | 태스크 상태 조회 |
| `PUT /v2/workflow/resume-task` | 일시정지된 태스크 재개 |
| `GET /v2/workflow/list-official-workflow-templates` | 공식 템플릿 목록 |

### 빠른 시작 (Python)

```bash
pip install requests
```
```python
import os, requests
headers = {"Authorization": os.getenv("BROWSERACT_API_KEY")}
# 템플릿으로 실행
requests.post("https://api.browseract.com/v2/workflow/run-task-by-template", headers=headers, json={"templateId": "...", "input": {...}})
```

### 설정

1. [BrowserAct Integrations](https://www.browseract.com/reception/integrations)에서 API 키 발급
2. 환경변수: `BROWSERACT_API_KEY=app-xxxxx`
3. [Workflow List](https://www.browseract.com/reception/workflow-list)에서 Workflow ID 확인

> **Agent-Reach와 함께 사용**: 읽기/검색은 Agent-Reach, 로그인 후 웹 조작·폼 제출 등 고마찰 구간은 BrowserAct로 역할 분담.

---

## 15. anthropics/skills — 공식 Anthropic 스킬 컬렉션

> 출처: https://github.com/anthropics/skills
> 설치: `npx skills add anthropics/skills@<skill-name>`

Anthropic 공식 제공 스킬 17종. 창작·문서·개발·엔터프라이즈 워크플로우 커버.

| 스킬 | 설명 |
|---|---|
| `algorithmic-art` | 알고리즘 아트 생성 |
| `brand-guidelines` | 브랜드 가이드라인 적용 |
| `canvas-design` | Canvas 기반 디자인 |
| `claude-api` | Claude API 코드 생성 |
| `doc-coauthoring` | 문서 공동 저작 |
| `docx` | Word 문서 생성/편집 |
| `frontend-design` | 프론트엔드 UI 디자인 |
| `internal-comms` | 사내 커뮤니케이션 |
| `mcp-builder` | MCP 서버 생성 |
| `pdf` | PDF 생성/처리 |
| `pptx` | PowerPoint 생성 |
| `skill-creator` | 새 스킬 작성 보조 |
| `slack-gif-creator` | Slack GIF 생성 |
| `theme-factory` | 테마/색상 팔레트 생성 |
| `web-artifacts-builder` | 웹 아티팩트 빌더 |
| `webapp-testing` | 웹앱 자동 테스트 |
| `xlsx` | Excel 파일 생성/처리 |

---

## 16. ComposioHQ/awesome-claude-skills — 1000+ 스킬 큐레이션 컬렉션

> 출처: https://github.com/ComposioHQ/awesome-claude-skills
> 설치: `npx skills add ComposioHQ/awesome-claude-skills@<skill-name>`

1000+ 실전 스킬 + **500+ 앱 연동** (이메일 발송, GitHub 이슈 생성, Slack 전송 등 실제 액션 수행).

**핵심 플러그인 — connect-apps:**
```bash
claude --plugin-dir ./connect-apps-plugin
/connect-apps:setup   # API 키 입력 (dashboard.composio.dev)
```

**주요 스킬 카테고리:**

| 스킬 | 설명 |
|---|---|
| `artifacts-builder` | 웹 아티팩트 빌더 |
| `changelog-generator` | 변경 이력 자동 생성 |
| `competitive-ads-extractor` | 경쟁사 광고 분석 추출 |
| `content-research-writer` | 콘텐츠 리서치·작성 |
| `developer-growth-analysis` | 개발자 성장 분석 |
| `domain-name-brainstormer` | 도메인명 아이디어 생성 |
| `file-organizer` | 파일 정리 자동화 |
| `image-enhancer` | 이미지 품질 향상 |
| `invoice-organizer` | 인보이스 정리 |
| `lead-research-assistant` | 리드 리서치 |
| `meeting-insights-analyzer` | 회의록 분석 |
| `tailored-resume-generator` | 맞춤 이력서 생성 |
| `twitter-algorithm-optimizer` | 트위터 알고리즘 최적화 |
| `video-downloader` | 영상 다운로드 |

---

## 17. JimLiu/baoyu-skills — 콘텐츠·미디어·소셜 스킬 21종

> 출처: https://github.com/JimLiu/baoyu-skills
> 설치: `npx skills add jimliu/baoyu-skills` 또는 `npx skills add jimliu/baoyu-skills@<skill-name>`

AI 에이전트(Claude Code, Codex 등)로 콘텐츠 제작·SNS 배포 워크플로우를 자동화하는 21개 스킬.

| 스킬 | 설명 |
|---|---|
| `baoyu-article-illustrator` | 기사 일러스트 자동 생성 |
| `baoyu-comic` | 만화 생성 |
| `baoyu-compress-image` | 이미지 압축 |
| `baoyu-cover-image` | 커버 이미지 생성 |
| `baoyu-diagram` | 다이어그램 생성 |
| `baoyu-image-gen` | 이미지 생성 |
| `baoyu-infographic` | 인포그래픽 생성 |
| `baoyu-markdown-to-html` | Markdown → HTML 변환 |
| `baoyu-post-to-wechat` | 위챗 공식 계정 발행 |
| `baoyu-post-to-weibo` | 웨이보 포스팅 |
| `baoyu-post-to-x` | X(트위터) 포스팅 |
| `baoyu-slide-deck` | 슬라이드 덱 생성 |
| `baoyu-translate` | 번역 |
| `baoyu-url-to-markdown` | URL → Markdown 변환 |
| `baoyu-wechat-summary` | 위챗 기사 요약 |
| `baoyu-xhs-images` | 샤오홍슈 이미지 생성 |
| `baoyu-youtube-transcript` | YouTube 자막 추출 |

---

## 18. stellarlinkco/myclaude — 멀티 에이전트 오케스트레이션 워크플로우

> 출처: https://github.com/stellarlinkco/myclaude
> 설치: `npx github:stellarlinkco/myclaude`
> 지원 런타임: Claude Code · Codex · Gemini · OpenCode

멀티백엔드 멀티 에이전트 개발 자동화 시스템. 6개 모듈로 구성.

| 모듈 | 명령 | 설명 |
|---|---|---|
| `do` | `/do` | ★추천 — 5단계 피처 개발 (codeagent 오케스트레이션) |
| `omo` | `/omo` | 인텔리전트 라우팅 멀티 에이전트 오케스트레이션 |
| `bmad` | `/bmad-pilot` | BMAD 애자일 워크플로우 (6개 전문 에이전트) |
| `requirements` | `/requirements-pilot` | 경량 요구사항→코드 파이프라인 |
| `essentials` | `/code`, `/debug` 등 | 11개 핵심 개발 명령 (ask/bugfix/code/debug/docs/enhance-prompt/optimize/refactor/review/test/think) |
| `sparv` | `/sparv` | Specify→Plan→Act→Review→Vault 워크플로우 |

---

## 19. WangBaoHe333/claude-code-skills-hub — 898개 스킬 검색·배치 설치 허브

> 출처: https://github.com/WangBaoHe333/claude-code-skills-hub
> 웹 UI: http://39.104.27.129/skills/

위 소스들(anthropics/skills, baoyu-skills, awesome-claude-skills, myclaude)의 898개 스킬을 **한 곳에서 검색·선택·배치 다운로드**할 수 있는 집계 플랫폼.

- 중문/영문 이중 언어 UI
- 이름·용도·시나리오·태그 검색
- 여러 스킬 선택 후 "导出 ccswitch ZIP" 일괄 내보내기 → CC Switch(#20)로 가져오기
- 각 스킬 상세에 출처·원본 설명·라이선스 표시

---

## 20. CC Switch — Claude Code 올인원 관리 데스크톱 앱 (farion1231)

> 출처: https://github.com/farion1231/cc-switch
> 공식 사이트: https://ccswitch.io
> 최신 버전: v3.16.5 (Windows: `CC-Switch-v3.16.5-Windows.msi` / `Windows-Portable.zip`)

Claude Code, Claude Desktop, Codex, Gemini CLI, OpenCode, OpenClaw, Hermes 7개 도구를 **한 앱에서 통합 관리**하는 크로스 플랫폼 데스크톱 앱.

### 핵심 기능
- **통합 MCP & Skills 관리** — Claude Code 포함 모든 AI 도구의 MCP 서버·스킬을 단일 패널에서 관리, 양방향 동기화
- **50+ 프로바이더 프리셋** — AWS Bedrock, NVIDIA NIM, 커뮤니티 릴레이 등 원클릭 전환
- **시스템 트레이 빠른 전환** — 실행 중에도 API 프로바이더 즉시 교체
- **ccswitch ZIP 가져오기** — 스킬 허브(http://39.104.27.129/skills/)에서 내보낸 ZIP을 한번에 가져오기

### 스킬 허브 배치 설치 순서
1. CC Switch 설치: https://github.com/farion1231/cc-switch/releases/latest
2. 스킬 허브(http://39.104.27.129/skills/)에서 원하는 스킬 선택 → "导出 ccswitch ZIP"
3. CC Switch → Skills 패널 → ZIP 가져오기

### 스킬 개별 설치 (npx 방식)
```bash
# Anthropic 공식
npx skills add anthropics/skills@<skill-name>
# Composio
npx skills add ComposioHQ/awesome-claude-skills@<skill-name>
# 宝玉
npx skills add jimliu/baoyu-skills@<skill-name>
# 설치 경로
# Windows: C:\Users\<user>\.claude\skills\<skill-name>\SKILL.md
```

---

## 21. SGLang — LLM 고성능 서빙 프레임워크 (sgl-project)

> 출처: https://github.com/sgl-project/sglang
> 설치: `pip install uv && uv pip install --prerelease=allow sglang`

대규모 언어 모델·멀티모달 모델을 위한 고성능 서빙 프레임워크. RadixAttention 프리픽스 캐싱으로 낮은 지연·높은 처리량 제공.

### 핵심 기능
- **RadixAttention** — 프리픽스 캐싱 + 제로 오버헤드 CPU 스케줄러
- **광범위 모델 지원** — Llama, Qwen, DeepSeek 등 주요 오픈소스 LLM
- **다양한 하드웨어** — NVIDIA, AMD, Intel, Google TPU, Ascend NPU
- **구조화 출력** — JSON/FSM 기반 Function Calling(Tool Use) 지원
- **RL 통합** — verl 등 포스트트레이닝 프레임워크 네이티브 연동

### Claude Code 연결 (로컬 LLM 백엔드)

```bash
# 서버 시작
python -m sglang.launch_server --model-path <모델경로> --host 0.0.0.0 --port 30000

# 환경변수 설정
export ANTHROPIC_BASE_URL=http://127.0.0.1:30000
export ANTHROPIC_AUTH_TOKEN=dummy
export CLAUDE_CODE_ATTRIBUTION_HEADER=0        # 멀티턴 프리픽스 캐시 필수
export ANTHROPIC_DEFAULT_SONNET_MODEL=<모델명>
export ANTHROPIC_DEFAULT_HAIKU_MODEL=<모델명>
```

> `CLAUDE_CODE_ATTRIBUTION_HEADER=0` 설정이 멀티턴 대화 프리픽스 캐시 재사용에 필수.

---

## 22. Serena — AI 에이전트를 위한 의미론적 IDE (oraios)

> 출처: https://github.com/oraios/serena
> 설치: `uv tool install -p 3.13 serena-agent && serena init`
> 문서: https://oraios.github.io/serena/

MCP로 Claude Code에 연결하는 **에이전트 전용 IDE**. 40개+ 언어에서 파일 수준이 아닌 **심볼 수준** 코드 조작 제공.

### 핵심 기능

- **의미론적 심볼 검색** — find symbol, symbol overview, 타입 계층, 참조 추적
- **심볼 수준 편집** — 본문 교체, 심볼 전후 삽입, 안전한 삭제, 정규식 교체
- **크로스파일 리팩토링** — 이름 변경, 파일/디렉토리 이동, 미사용 코드 제거
- **에이전트 메모리 시스템** — 작업 컨텍스트 지속 유지
- **JetBrains 플러그인** — 대화형 디버깅 확장

### Claude Code 연결

```bash
# 설치
uv tool install -p 3.13 serena-agent
serena init

# Claude Code settings.json MCP 등록
# "launch" 방식 또는 HTTP URL 방식 선택
```

> Claude Code 기본 파일 편집을 심볼 수준으로 보완하는 강력한 MCP 도구.

---

## 23. 하네스 엔지니어링 참고 자료

### Mitchell Hashimoto의 AI 도입 6단계 여정
> https://mitchellh.com/writing/my-ai-adoption-journey

HashiCorp 공동창업자의 실전 AI 도입 방법론. Claude Code를 메인 에이전트로 사용하며 하네스를 발전시킨 경험담.

**핵심 단계:**
1. 웹 챗봇 버리고 파일 읽기/실행 가능 에이전트로 전환
2. 같은 작업을 직접 + 에이전트로 병행하며 위임 전략 습득
3. 업무 종료 30분 전에 에이전트를 리서치·이슈 정리·PR 검토에 투입
4. AGENTS.md + 커스텀 도구로 에이전트 오류 방지 (하네스 엔지니어링)
5. 항상 최소 1개 에이전트 상시 운영 → 업무 선택 자유도 향상

**활용 포인트:** CLAUDE.md = AGENTS.md 역할. 커스텀 도구 + 스킬로 하네스 구성.

---

## 24. MCP 서버 현황 (설치됨, 2026-07-09)

> **실제 설정 파일: `C:\Users\user\.claude.json`** → `mcpServers` (Claude Code가 읽는 파일)
> 참고용 미러: `C:\Users\user\.claude\settings.json` → `mcpServers` (CC Switch 등 외부 도구용)

### Python/uvx 기반 (즉시 사용)
| 서버명 | 설명 | 명령 |
|---|---|---|
| `fetch` | 웹 페이지 가져오기 → Markdown 변환 | `uvx mcp-server-fetch` |
| `git` | Git 저장소 읽기·검색·조작 | `uvx mcp-server-git` |
| `time` | 시간 조회·타임존 변환 | `uvx mcp-server-time` |
| `sqlite` | SQLite DB 조작 | `uvx mcp-server-sqlite` |

### Node.js/npx 기반 (공식 @modelcontextprotocol)
| 서버명 | 설명 | 패키지 |
|---|---|---|
| `filesystem` | 파일 시스템 접근 (`C:\Users\user` 기준) | `@modelcontextprotocol/server-filesystem` |
| `memory` | 지식 그래프 기반 영구 메모리 | `@modelcontextprotocol/server-memory` |
| `sequential-thinking` | 단계적 추론·문제해결 | `@modelcontextprotocol/server-sequential-thinking` |
| `github` | GitHub API ★ | `@modelcontextprotocol/server-github` |
| `brave-search` | Brave 검색 ★ | `@modelcontextprotocol/server-brave-search` |
| `puppeteer` | Puppeteer 브라우저 자동화 | `@modelcontextprotocol/server-puppeteer` |
| `everything` | MCP 기능 전체 데모 서버 | `@modelcontextprotocol/server-everything` |
| `slack` | Slack 메시지·채널 조작 ★ | `@modelcontextprotocol/server-slack` |

### Node.js/npx 기반 (서드파티)
| 서버명 | 설명 | 패키지 |
|---|---|---|
| `context7` | 최신 라이브러리 공식 문서 조회 | `@upstash/context7-mcp` |
| `playwright` | Microsoft Playwright 브라우저 자동화 | `@playwright/mcp` |
| `notion` | Notion API ★ | `@notionhq/notion-mcp-server` |
| `exa` | Exa AI 시맨틱 검색 ★ | `exa-mcp-server` |
| `chart` | AntV 기반 25종 차트 생성 | `@antv/mcp-server-chart` |
| `ScraplingServer` | 웹 스크래핑 (반봇 우회·브라우저 자동화) | `scrapling mcp` |

### claude.ai 연동 (자동)
| 서버명 | 설명 |
|---|---|
| `claude.ai Google Drive` | Google Drive 파일 접근 |
| `claude.ai Gmail` | Gmail 읽기·작성 |
| `claude.ai Google Calendar` | Google Calendar 조작 |
| `claude.ai Canva` | Canva 디자인 생성·편집 |

**★ API 키 필요:** `.claude.json` → `mcpServers.<name>.env` 에서 설정
- `github`: `GITHUB_PERSONAL_ACCESS_TOKEN`
- `brave-search`: `BRAVE_API_KEY`
- `notion`: `OPENAPI_MCP_HEADERS` (Bearer Notion token)
- `exa`: `EXA_API_KEY`
- `slack`: `SLACK_BOT_TOKEN` + `SLACK_TEAM_ID`

---

## 25. 설치된 스킬 현황 (64개, 2026-07-09 기준)

> 설치 경로: `C:\Users\user\.claude\skills\`

### anthropics/skills (17개)
`algorithmic-art` · `brand-guidelines` · `canvas-design` · `claude-api` · `doc-coauthoring` · `docx` · `frontend-design` · `internal-comms` · `mcp-builder` · `pdf` · `pptx` · `skill-creator` · `slack-gif-creator` · `theme-factory` · `web-artifacts-builder` · `webapp-testing` · `xlsx`

### jimliu/baoyu-skills (19개)
`baoyu-article-illustrator` · `baoyu-codex-imagegen` · `baoyu-comic` · `baoyu-compress-image` · `baoyu-cover-image` · `baoyu-diagram` · `baoyu-fetch` · `baoyu-image-gen` · `baoyu-infographic` · `baoyu-markdown-to-html` · `baoyu-post-to-wechat` · `baoyu-post-to-weibo` · `baoyu-post-to-x` · `baoyu-slide-deck` · `baoyu-translate` · `baoyu-url-to-markdown` · `baoyu-wechat-summary` · `baoyu-xhs-images` · `baoyu-youtube-transcript`

### ComposioHQ/awesome-claude-skills (13개)
`artifacts-builder` · `changelog-generator` · `competitive-ads-extractor` · `content-research-writer` · `developer-growth-analysis` · `domain-name-brainstormer` · `file-organizer` · `image-enhancer` · `invoice-organizer` · `lead-research-assistant` · `meeting-insights-analyzer` · `tailored-resume-generator` · `twitter-algorithm-optimizer`

### stellarlinkco/myclaude (13개)
`browser` · `codeagent` · `codeagent-wrapper` · `dev` · `do` · `harness` · `omo` · `product-requirements` · `prototype-prompt-generator` · `skill-install` · `skills` · `sparv` · `test-cases`

### 기타 (3개)
`ad-studio` · `ouroboros` · `hwpx`

---

## 26. alirezarezvani/claude-skills — 355개 프로덕션 레디 스킬 & 602개 CLI 도구

> 출처: https://github.com/alirezarezvani/claude-skills
> ⭐ 21.7k stars

355개 프로덕션 레디 스킬 + 602개 CLI 도구 (의존성 없음). 18개 도메인 커버. Claude Code, Codex, Gemini CLI, Cursor 등 13개 AI 도구 지원.

### 설치

```
/plugin marketplace add alirezarezvani/claude-skills
/plugin install engineering-skills@claude-code-skills
```

### 18개 도메인 (주요)

| 도메인 | 스킬 수 | 예시 |
|---|---|---|
| 엔지니어링 코어 | 52개 | RAG 아키텍트, DB 설계자, MCP 빌더 |
| 엔지니어링 POWERFUL | 81개 | CI/CD 파이프라인, 보안 감사자, 성능 프로파일러 |
| 마케팅 | 48개 | SEO, 콘텐츠, 성장 해킹 |
| C-레벨 어드바이저리 | 68개 | CEO·CTO·CISO 역할 수행 |
| 규제/품질 | 19개 | FDA, ISO, GDPR 컴플라이언스 |
| 연구 | 14개 | 학술 연구, 운영 리서치 |

### 오케스트레이션 기능
- 3개 사전 구성 페르소나 (Startup CTO, 성장 마케터 등)
- 멀티 스킬·에이전트 조율 프로토콜

---

## 27. travisvn/awesome-claude-skills — 큐레이션된 스킬 목록

> 출처: https://github.com/travisvn/awesome-claude-skills
> ⭐ 14k stars

Claude Code 스킬·리소스·도구를 큐레이션한 awesome 리스트. 공식 스킬 + 커뮤니티 스킬 + 가이드 포함.

**핵심 링크**: 새로운 스킬 발견 시 이 레포 먼저 확인.

---

## 28. Claude Code 프로젝트 구조 최적 설정

> 최대 컨텍스트, 모듈화, 자율성을 위한 베스트 프랙티스

### 프로젝트 루트 구조

```
프로젝트루트/
├── CLAUDE.md          ← 전역 지침 (200줄 이하 권장)
├── CLAUDE.local.md    ← 로컬 개인 설정 (gitignore)
├── AGENTS.md          ← 에이전트 전용 가이드
├── mcp.json           ← MCP 서버 설정
├── .worktreeinclude   ← worktree 포함 파일 목록
└── .claude/
    ├── settings.json
    ├── settings.local.json
    ├── rules/
    │   ├── testing.md
    │   ├── api-design.md
    │   └── frontend/
    │       └── react.md
    ├── skills/
    │   ├── security-review/
    │   │   ├── SKILL.md
    │   │   └── checklist.md
    │   └── deploy/
    │       ├── SKILL.md
    │       └── changelog.tmpl
    ├── agents/
    │   ├── code-reviewer.md
    │   ├── debugger.md
    │   └── db-validator.md
    ├── workflows/
    │   └── release-train.js
    ├── hooks/
    │   ├── format.sh
    │   ├── protect.sh
    │   ├── output-styles/
    │   └── review-mode.md
    ├── docs/
    │   ├── architecture.md
    │   └── decisions/
    └── tools/
        └── scripts/claude.py
```

### 컨텍스트 사다리 (4단계)

| 단계 | 파일 | 로드 시점 |
|---|---|---|
| 1 모든 세션 | `CLAUDE.md` + 규칙 | 항상 (경로 없음) |
| 2 경로 기반 | `rules/*.md` | 자연 로드 (경로 매칭) |
| 3 호출 시 | `skills/*` via `/이름` | 필요할 때 |
| 4 격리 수준 | 에이전트 & 워크플로우 | 자체 컨텍스트 |

### 지침 vs 강제 규칙

| 구분 | 적용 방법 | 설명 |
|---|---|---|
| **지침** (CLAUDE.md / rules) | 요청 사항 | Claude가 읽고 일반적으로 따름. 대화, 명령, 아키텍처 컨텍스트를 이해함. |
| **강제 규칙** (settings + hooks) | 강제 사항 | `permissions.deny`, `rm -rf` 차단, Claude가 무화하거나 우회할 수 없음. `PostToolUse` 형식은 모든 편집에 적용. |

### 에이전트 계층

- **서브 에이전트** — 고품질 프롬프트, 도구, 모델, 에러리 구성된 독립 프롬프트
- **워크플로우** — `agents/*.js` 형태의 여러 서브 에이전트를 하나의 워크플로우로 오케스트레이션
- **worktree** — `.worktreeinclude` 격리된 체크아웃에서 여러 에이전트를 병렬로 실행 (`.env` 포함)

### 핵심 팁

- **CLAUDE.md는 200줄 이하**로 (npm test, build, lint), 작업을 검증할 수 있어야 함
- **비용**: `${ENV_VAR}로` 관리, `mcp.json`에 기록하여 공유
- **gitignore**: `.claude/settings.local.json` • `.worktreeinclude` • `~/.claude/projects/` 에 메모리/설정 기록
- **에이전트 & 워크플로우**: `agents/` 폴더로 팀 전원이 공유
- **Hooks**: `settings.json`에 연결된 스크립트로 도구 전에·후에 가이드라인을 자동 적용

---

## 29. 2026년 추천 GitHub 저장소 10선 — AI 노트북 실행

> 출처: 이미지 큐레이션 (2026년 기준)
> "세계 최고의 지식을 AI로 내 노트북에서 실행하기"

| # | 저장소 | 별점 | 설명 |
|---|---|---|---|
| 1 | [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | ~190k | Karpathy 관찰 기반 Claude Code 동작 개선 단일 CLAUDE.md |
| 2 | [MemPalace/mempalace](https://github.com/MemPalace/mempalace) | ~57k | 최고 벤치마크 오픈소스 AI 메모리 시스템 |
| 3 | [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | ~91k | 단일 GPU에서 nanochat 학습을 자동화하는 AI 연구 루프 |
| 4 | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | ~50k | Claude Code 최고 스킬·에이전트·플러그인·도구 큐레이션 |
| 5 | [SuperClaude-Org/SuperClaude_Framework](https://github.com/SuperClaude-Org/SuperClaude_Framework) | ~24k | 전문 명령어·인지 페르소나·개발 방법론으로 Claude Code 강화 |
| 6 | [microsoft/ai-agents-for-beginners](https://github.com/microsoft/ai-agents-for-beginners) | ~69k | AI 에이전트 구축 입문 12강 Microsoft 공식 코스 |
| 7 | [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | ~118k | 직접 실행 가능한 100+ AI 에이전트 및 RAG 앱 모음 |
| 8 | [mattpocock/skills](https://github.com/mattpocock/skills) | ~165k | 실전 엔지니어를 위한 Claude Code 스킬 모음 |
| 9 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | ~213k | 사용자와 함께 성장하는 자기 발전형 AI 에이전트 |
| 10 | [microsoft/qlib](https://github.com/microsoft/qlib) | ~46k | AI 기술로 퀀트 리서치를 지원하는 AI 지향 퀀트 투자 플랫폼 |

### 설치 참고

- **andrej-karpathy-skills**: `CLAUDE.md` 파일 하나만 복사하면 즉시 적용
- **SuperClaude Framework**: `/install-superclaude` 로 설치 후 18개 슬래시 커맨드 사용
- **MemPalace**: `pip install mempalace` + MCP 서버 등록
- **autoresearch**: 단일 GPU (RTX 3090+) 필요, `pip install autoresearch`
- **awesome-llm-apps / awesome-claude-code**: 각 앱/스킬 README 참고
- **hermes-agent**: `pip install hermes-agent` + Nous API 키 필요

---

## 30. Orca — 100x 빌더를 위한 AI 에이전트 오케스트레이터 (stablyai)

> 출처: https://github.com/stablyai/orca
> ⭐ 18.3k stars · 공식 사이트: onorca.dev

여러 AI 에이전트를 **병렬 git 워크트리**에서 동시 실행하고 한 화면에서 추적·비교·병합하는 ADE(에이전트 개발 환경).

### 지원 에이전트 (30+종)
Claude Code · Codex · Grok · Cursor · GitHub Copilot · OpenCode · Antigravity · Pi · Devin · Cline · Codebuff · Kimi · Qwen Code 등 **CLI에서 실행되는 모든 에이전트** 지원

### 핵심 기능

| 기능 | 설명 |
|---|---|
| **병렬 워크트리** | 단일 프롬프트를 5개 에이전트에 분산 → 결과 비교 후 승자 병합 |
| **터미널 스플릿** | WebGL 렌더링, 재시작 후에도 스크롤백 유지 |
| **디자인 모드** | 실제 Chromium 창 UI 클릭 → HTML·CSS·스크린샷 에이전트 프롬프트로 직접 전송 |
| **GitHub & Linear** | PR·이슈·프로젝트 보드 인앱, 작업→워크트리 직접 열기 |
| **SSH 워크트리** | 원격 머신에서 에이전트 실행 (자동 재연결·포트 포워딩) |
| **AI Diff 주석** | Diff 라인 코멘트 → 리뷰·편집·커밋 Orca 내에서 완결 |
| **파일 드래그** | VS Code 에디터 + 파일·이미지 → 에이전트 프롬프트로 드래그 |
| **모바일 앱** | iOS(App Store/TestFlight) · Android(APK) — 핸드폰에서 에이전트 모니터링·조종 |

### Orca CLI 주요 명령

```bash
orca worktree create   # 새 워크트리 생성
orca snapshot          # 워크트리 스냅샷
orca click             # UI 요소 클릭 자동화
orca fill              # 폼 입력 자동화
```

### 설치

```bash
# macOS (Homebrew)
brew install --cask stablyai/orca/orca

# Arch Linux (AUR)
yay -S stably-orca-bin

# Windows / Linux: GitHub Releases에서 직접 다운로드
# https://github.com/stablyai/orca/releases/latest
```

---

## 31. LLM Wiki 세컨드 브레인 — Karpathy × Obsidian × Graphify

> 출처: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

**"RAG는 매번 검색해서 답을 만든다. LLM Wiki는 지식이 쌓여서 답이 더 좋아진다. 개인 지식관리에는 검색이 아니라 축적이 필요하다."**

개인 지식을 Obsidian 볼트에 체계적으로 모으고, Claude Code가 읽고 활용하는 AI 세컨드 브레인 워크플로우.

### 필요 도구

| 도구 | 역할 |
|---|---|
| Obsidian | 볼트 생성 (https://obsidian.md) |
| Claude Code | 데스크탑 앱 또는 터미널, 볼트 폴더에 연결 |
| Obsidian Web Clipper | Chrome 확장 프로그램 — 수집 자동화 |
| Graphify | `pip install graphifyy` — 지식 그래프 시각화 |

### 사전 숙제 3가지 (한 줄씩이면 충분)

1. **나는 누구인가** — 이름, 하는 일, 역할
2. **왜 기록하고 싶은가** — 지금 뭐가 안 되는지, 기록이 되면 뭐가 달라지는지
3. **어떤 아웃풋을 만들고 싶은가** — 누구를 위해, 어떤 형태로

> Gold In, Gold Out — 목적 없이 수집하면 쓰레기 데이터.

### 7단계 워크플로우

| 단계 | 설명 | 핵심 산출물 |
|---|---|---|
| Step 1 | 맥락 인터뷰 — AI가 나를 깊이 파악 | `나의 핵심 맥락.md` |
| Step 2 | CLAUDE.md 생성 — AI가 읽는 나의 설명서 | `CLAUDE.md` (볼트 내) |
| Step 3 | LLM Wiki 세팅 — 폴더 구조 + 위키 스키마 | `wiki/` 구조 |
| Step 4 | 웹 클리퍼 템플릿 — 수집 자동화 | 커스텀 JSON 템플릿 |
| Step 5 | 인제스트 — 수집한 것을 나의 지식으로 | `wiki/` 반영 |
| Step 6 | 스킬 만들기 — 반복 작업 자동화 | `/ingest` `/query` `/lint` |
| Step 7 | Graphify — 지식을 그래프로 | `graphify-out/` |

### Karpathy LLM Wiki 핵심 규칙 10가지

1. `raw/`는 절대 수정 금지 (불변 원본)
2. wiki 페이지 생성/삭제 시 `index.md` 필수 업데이트
3. 모든 오퍼레이션마다 `log.md`에 기록
4. 내부 참조는 `[[wikilink]]` 형식
5. 모든 wiki 페이지에 YAML frontmatter
6. 모순 발견 시 양쪽 소스 모두 인용
7. 소스 요약은 사실만, 해석은 개념 페이지에서
8. 질의 시 `index.md` 먼저, `raw/`는 마지막 수단
9. 새 페이지보다 기존 페이지 업데이트 우선
10. index 항목은 한 줄, 120자 이내

### 볼트 구조

```
볼트/
├── CLAUDE.md              ← 나의 설명서 + 위키 운영 규칙
├── 나의 핵심 맥락.md       ← 맥락 인터뷰 결과
├── raw/                   ← 불변 원본 (수집한 자료, 절대 수정 금지)
│   ├── articles/
│   ├── videos/
│   └── ...
├── wiki/                  ← 가공된 지식 (AI가 편집)
│   ├── index.md
│   ├── log.md
│   └── ...
└── graphify-out/          ← 그래프 데이터 (Graphify 생성)
    ├── graph.json
    ├── graph.html
    └── GRAPH_REPORT.md
```

### 핵심 스킬 명령

**인제스트 (빠른 버전):**
```
raw/ 폴더를 스캔해서 아직 인제스트 안 된 파일을 모두 처리해줘.
대화 없이 바로 wiki/에 반영하고, 끝나면 요약을 보여줘.
```

**스킬 생성 프롬프트:**
- `/ingest` — 새 파일 스캔 + wiki 반영 + log 기록
- `/query "질문"` — wiki 문서 기반 답변 (벡터DB 아님)
- `/lint` — 깨진 링크·미업데이트 항목 찾아 수정

**Graphify 실행:**
```bash
pip install graphifyy
/graphify wiki/            # 전체 그래프 생성
/graphify wiki/ --update   # 증분 업데이트 (토큰 절약)
/graphify query "질문"     # 그래프 기반 관계형 질의
```

### 참고 링크

- Karpathy LLM Wiki: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Graphify: https://github.com/graphifyy/graphify
- Obsidian Web Clipper: Chrome 웹스토어에서 "Obsidian Web Clipper" 검색

---

## 32. ckdshop / ckdshop2 구현 이력 (2026-07-17 기준)

> 프로젝트 경로: `C:\Users\user\Desktop\ckdshop\` (8082/PostgreSQL/5173) | `C:\Users\user\Desktop\ckdshop2\` (8083/MySQL/5174)
> **브랜드명: 종근당몰** (종근당쇼핑에서 변경)
> **철저 분리 원칙**: 두 프로젝트 코드 절대 혼합 금지. 커밋·푸시도 별도로.

### 공통 적용 기능 (양쪽 모두 구현 완료)

| 기능 | 핵심 파일 | 커밋 (ckdshop / ckdshop2) |
|---|---|---|
| **회원 탈퇴 + 개인정보 익명화** | `Member.withdraw()`, `MemberService.withdraw()`, `DELETE /mypage/withdraw` | d2a446a / c991556 |
| **탈퇴 회원 로그인 차단** | `MemberService.login()` — WITHDRAWN 상태 체크 | 동상 |
| **탈퇴 다이얼로그 (프론트)** | `MyPageView.vue` — 비밀번호 확인 후 탈퇴 | 동상 |
| **웹 스크래핑 방지** | `SuspiciousIpService`, `BotDetectionFilter`, `HoneypotController` | b964b99 / 8b42160 |
| **공개 API Rate Limit 강화** | `RateLimitFilter` — products/categories 60req/min | 동상 |
| **보안 헤더 추가** | `SecurityConfig` — Permissions-Policy, X-Permitted-Cross-Domain-Policies | 동상 |
| **Pinia 스토어 테스트** | `auth.test.js`, `cart.test.js` (Vitest 14개) | 동상 |
| **robots.txt** | AI 크롤러 및 API 경로 크롤링 차단 | 동상 |
| **통합 테스트 스크립트** | `run-all-tests.ps1` — 백엔드+프론트엔드 한 번에 실행 | d775a9c / caa9b94 |
| **테스트 전체 출력** | `build.gradle` testLogging + `run-all-tests.ps1` --console=plain/--reporter=verbose | bc29af0 / 23b7385 |
| **SSH 터널링 + 공개키 인증** | `SshTunnelService`, `SshTunnelConfig`, `SshAuditLogger` — JSch 기반 포트포워딩 | 6bd4e28 / b35cb89 |
| **Redis 정리 try-catch** | `SecurityIntegrationTest.@BeforeEach` — 연결 리셋 간헐 오류 방지 | 9de83d0 / e1363bc |

### SecurityIntegrationTest 구성 (16개 도메인)

| 도메인 | 설명 |
|---|---|
| 01 | 보안 HTTP 헤더 (X-Frame-Options, CSP, Referrer-Policy) |
| 02 | BCrypt 비밀번호 저장 |
| 03 | XSS·SQL 인젝션 입력 검증 |
| 04 | JWT 서명 검증 (변조/만료/악성 토큰) |
| 05 | CORS 정책 |
| 06 | 인증·세션 통제 (로그아웃 블랙리스트) |
| 07 | RBAC 관리자 권한 분리 |
| 08 | 데이터 격리 (본인 데이터만) |
| 09 | 개인정보 마스킹 |
| 10 | 감사 로그 |
| 11 | Rate Limiting |
| 12 | CSPM (Actuator 노출 범위) |
| 13 | 개인정보 수명주기 (INACTIVE/BLOCKED) |
| 14 | 법적 고지 (필수 항목·중복 가입) |
| 15 | 웹 스크래핑 방지 (봇 탐지·허니팟·보안 헤더) |
| 16 | 파일 업로드 보안 (매직바이트·이중확장자·악성파일) |

### ckdshop 전용 — 공통처리 종단관심사(AOP) 아키텍처

| 모듈 | 파일 | 역할 |
|---|---|---|
| **요청 로깅 필터** | `RequestLoggingFilter.java` (@Order 0) | MDC 상관 ID(X-Correlation-Id) 주입, 요청/응답 처리 시간 기록 |
| **서비스 실행 시간 Aspect** | `LoggingAspect.java` | @Service 메서드 자동 측정, 500ms 초과 시 WARN |
| **선언적 감사 로그** | `@AuditLog` + `AuditAspect.java` | 어노테이션만 붙이면 AuditLogService 자동 호출 |
| **글로벌 예외 핸들러** | `GlobalExceptionHandler.java` | HttpStatus 전파, Spring Security 예외(401/403) 통합 처리 |
| **에러 코드** | `ErrorCode.java` (37개) | 모든 코드에 HttpStatus 필드 추가 |
| **비즈니스 예외** | `BusinessException.java` | ErrorCode에서 HttpStatus 자동 주입 |

**필터 체인 순서**: `RequestLoggingFilter(@Order 0)` → `XssFilter(@Order 1)` → `RateLimitFilter(@Order 2)` → `JwtAuthFilter`

### SSH 터널링 아키텍처 (양쪽 공통)

- **라이브러리**: `com.github.mwiede:jsch:0.2.19`
- **활성화**: `SSH_TUNNEL_ENABLED=true` 환경변수 (기본 false — 로컬 개발은 직접 연결)
- **ckdshop**: 로컬 포트 15432 → 원격 PostgreSQL 5432
- **ckdshop2**: 로컬 포트 13306 → 원격 MySQL 3306
- **인증**: `~/.ssh/id_rsa` 공개키 (패스프레이즈 선택)
- **감사**: `ApplicationReadyEvent` → `SSH_TUNNEL_OPEN`, `ContextClosedEvent` → `SSH_TUNNEL_CLOSE` DB 기록

### 핵심 제약 사항
- 어드민 계정(`admin@ckdshop.com`) 비밀번호 임의 수정 금지
- ckdshop2 포트: 백엔드 8083, 프론트엔드 5174 (ckdshop은 8082/5173)
- `run-all-tests.ps1`로 백엔드+프론트 통합 실행 가능 (양쪽 모두 ALL PASS 확인 완료)

---

## 33. UI UX Pro Max — AI 디자인 인텔리전스 스킬 (nextlevelbuilder)

> 출처: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
> ⭐ 107k stars · Fork 11.3k
> 설치: `npx skills add nextlevelbuilder/ui-ux-pro-max-skill`

멀티플랫폼 UI/UX 구현을 위한 **디자인 인텔리전스 AI 스킬**. v2.0에서 161개 산업별 추론 규칙 기반 디자인 시스템 자동 생성 추가.

### 핵심 데이터베이스

| 항목 | 수량 | 설명 |
|---|---|---|
| UI 스타일 | 84종 | Glassmorphism, Claymorphism, Brutalism, Bento Grid, AI-Native UI 등 |
| 색상 팔레트 | 192종 | 192개 제품 유형과 1:1 매핑 |
| 폰트 조합 | 74종 | Google Fonts 임포트 포함 |
| 추론 규칙 | 161개 | 산업별 디자인 시스템 생성 (v2.0 신규) |
| UX 가이드라인 | 98개 | 베스트 프랙티스 + 안티패턴 + 접근성 |
| 차트 타입 | 25종 | 대시보드·분석 추천 |
| 기술 스택 | 22종 | React, Next.js, Vue, Nuxt, Flutter, SwiftUI, Jetpack Compose 등 |

### 디자인 시스템 생성 파이프라인 (v2.0 플래그십)

```
사용자 요청 → 5개 병렬 검색 (제품유형·스타일·팔레트·패턴·폰트)
→ 추론 엔진 (BM25 랭킹 + 안티패턴 필터)
→ 완성된 디자인 시스템 출력
  (패턴 + 스타일 + 색상 + 타이포그래피 + 이펙트 + 안티패턴 + 체크리스트)
```

### 지원 산업 카테고리 (일부)

- **Tech & SaaS**: SaaS, B2B, Developer Tool, AI/Chatbot, Cybersecurity
- **Finance**: Fintech, Banking, Insurance, Personal Finance
- **Healthcare**: Medical Clinic, Dental, Mental Health
- **E-commerce**: General, Luxury, Marketplace, Food Delivery
- **Services**: Beauty/Spa, Restaurant, Hotel, Legal
- **Creative**: Portfolio, Agency, Photography, Gaming

### 활용 시점

- 랜딩 페이지 / 대시보드 / 모바일 앱 UI 시작 전 디자인 시스템 결정이 필요할 때
- 산업/브랜드에 맞는 색상·폰트·스타일 조합을 빠르게 도출할 때
- 안티패턴(예: 뱅킹 서비스에 AI 보라/핑크 그라디언트 금지) 사전 필터링이 필요할 때

---

## 34. Scrapling — 적응형 고성능 웹 스크래핑 프레임워크 (D4Vinci)

> 출처: https://github.com/D4Vinci/Scrapling
> ⭐ 70.9k stars · Fork 7k · 라이선스: BSD-3-Clause

**"Undetectable. Adaptive. Powerful."** — 반봇 시스템 우회, 요소 자동 재배치, 브라우저 자동화를 하나로 통합한 Python 웹 스크래핑 프레임워크.

### 핵심 페처(Fetcher) 3종

| 페처 | 설명 | 용도 |
|---|---|---|
| `Fetcher` | 빠른 HTTP 요청 | 일반 정적 페이지 |
| `StealthyFetcher` | 은폐 모드, 반봇 우회 | Cloudflare 등 봇 감지 사이트 |
| `DynamicFetcher` | 완전한 브라우저 자동화 | JS 렌더링 필요 페이지 |

### 주요 특징

| 특징 | 설명 |
|---|---|
| **적응형 스크래핑** | 웹사이트 레이아웃 변경 시 요소 자동 재배치·추적 |
| **Scrapy 스타일 API** | 스파이더 클래스 기반 대규모 크롤링 지원 |
| **MCP 서버 내장** | Claude/Cursor 등 AI 에이전트와 직접 연동 |
| **일시중지·재개** | 크롤링 진행 상태 저장 후 재개 가능 |
| **멀티세션·동시성** | 병렬 요청 제어 내장 |
| **Cloudflare Turnstile 우회** | 자동 우회 기능 |

### 설치

```bash
# 기본
pip install scrapling

# 페처 포함 (권장)
pip install "scrapling[fetchers]"
scrapling install

# 전체 기능
pip install "scrapling[all]"
```

### 기본 사용법

```python
from scrapling.fetchers import Fetcher, StealthyFetcher

# 일반 요청
page = Fetcher.get('https://example.com')
data = page.css('.selector::text').getall()

# 반봇 우회
page = StealthyFetcher.fetch('https://protected-site.com')
```

### 스파이더 정의

```python
from scrapling.spiders import Spider

class MySpider(Spider):
    start_urls = ["https://example.com/"]

    async def parse(self, response):
        for item in response.css('.product'):
            yield {"title": item.css('h2::text').get()}

MySpider().start()
```

### 요구사항
- Python 3.10 이상
- Docker 이미지도 제공

---

## AI의 3가지 고질병 — 항상 경계

1. **잘못된 가정** — 코드를 읽기 전에 작동 방식을 가정하지 말 것
2. **코드 부풀리기** — 요청받지 않은 기능, 추상화, 오류 처리 추가 금지
3. **멋대로 고치기** — 요청 범위 밖의 코드 수정 금지
