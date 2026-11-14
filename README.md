# 생활문제 해결소 — 로또 당첨금 자동 갱신

동행복권 로또6/45의 최신 **1·2·3등 게임당 당첨금**을 주기적으로 수집·검증해 티스토리 「로또 당첨금 실수령액 계산기」에서 활용합니다.

- 공식 결과 화면: https://www.dhlottery.co.kr/lt645/result
- 원본 수집 경로는 동행복권 사이트 내부 JSON입니다. 공식 보장 API가 아니므로 변경·차단될 수 있습니다.
- `scripts/update_lotto.py`: 최신 결과 수집 및 검증
- `tests/test_update_lotto.py`: 검증 테스트
- `.github/workflows/update-lotto.yml`: 매주 토요일 저녁 및 매일 재확인
- `data/latest.json`: 최신 확인 회차의 공개 데이터
- 공개 데이터 주소 (GitHub Pages 설정 후): https://zeutioncom-arch.github.io/lotto-live-data/data/latest.json

**중요:** `data/latest.json`의 `status`가 `verified`로 바뀌기 전까지 초기 기록은 참고용입니다. 수집 실패 시 이전 파일은 보존하며, 실제 추첨 정보는 동행복권 공식 발표가 우선입니다.

### 1회 설정

저장소의 Settings → Pages → Deploy from a branch → `main` / `/(root)` 선택. Actions에서 `Update verified Lotto 6/45 result` 워크플로를 수동 실행하고, `data/latest.json`의 `status`와 회차를 확인한 다음 티스토리 계산기 HTML을 교체합니다.
