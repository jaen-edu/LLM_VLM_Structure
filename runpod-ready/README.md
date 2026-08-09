# RunPod 교육 운영 자동화 도구 (Python 3.12)

RunPod SDK와 openpyxl을 사용해 교육생/강사용 Pod를 운영하고, 접속 URL과 JupyterLab 접속 상태를 엑셀에 반영하는 도구입니다.

이 문서는 "GPU TYPE 조사 -> Pod 생성/검증 -> 수업 중 운영 -> 수업 종료 후 전체 Pod 제거"까지 실제 교육 운영 시나리오 순서로 작성되어 있습니다.

## 강사용 1페이지 빠른 운영 요약

인쇄용 문서가 필요하면 [docs/runpod-class-ops-1page-checklist.md](docs/runpod-class-ops-1page-checklist.md)를 사용하세요.

수업 당일에는 아래 순서대로 실행하면 됩니다.

### A. 수업 시작 전 10분

1. GPU 타입 확인

```powershell
python main.py --input "runpod-urls.xlsx" --list-gpu-types
```

2. 생성 시뮬레이션(dry-run)

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --dry-run --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

3. 실제 Pod 생성(접속 체크 생략, 빠름)

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

4. 접속 상태 일괄 확인

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

이 명령은 터미널에 번호/아이디/상태/URL을 표로 바로 출력하므로, 매번 엑셀 파일을 열지 않아도 현재 상태를 확인할 수 있습니다.

결과 파일 확인:

- `runpod-urls.xlsx`
- `RunPod URL`
- `JupyterLab 접속 가능 상태`
- `GPU Type`
- `SSH`

### B. 수업 중 운영

쉬는시간/점심시간 전체 중지:

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --all
```

특정 학생만 부분 제어(예시):

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --numbers 3 7
```

### C. 장애 대응

특정 학생 Pod 재생성(번호):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate 3 7 --overwrite-url
```

특정 학생 Pod 재생성(아이디):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate-ids user01 user02 --overwrite-url
```

웹에서 수동 변경한 상태 반영(sync):

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

### D. 수업 종료

비용 절감을 위한 전체 중지:

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --all
```

완전 종료(전체 Pod 제거):

```powershell
python main.py --input "runpod-urls.xlsx" --action terminate --all
python main.py --input "runpod-urls.xlsx" --action sync --all
```

운영 권장:

- `terminate --all` 후 `sync --all`까지 실행해 엑셀 상태를 최종 정합화합니다.

## 0. 용어 빠르게 이해하기

> GPU 타입 (GPU Type)
> RunPod에서 Pod 생성 시 선택하는 GPU 자원 종류입니다.
> 반대 개념: 고정된 단일 GPU만 강제 사용하는 운영
> 실무 연결: 수급 부족 시 폴백 GPU 타입을 함께 지정하면 수업 지연을 줄일 수 있습니다.

> 동기화 (Sync)
> RunPod 웹에서 수동 변경된 상태를 엑셀로 다시 반영하는 작업입니다.
> 반대 개념: 엑셀에 저장된 이전 상태를 그대로 신뢰
> 실무 연결: 운영자가 웹에서 급히 Pod를 삭제한 경우 반드시 sync로 문서를 맞춰야 합니다.

> 접속 상태 체크 (JupyterLab Health Check)
> 저장된 RunPod URL이 실제로 JupyterLab에 접속 가능한지 HTTP로 확인하는 단계입니다.
> 반대 개념: URL 문자열만 저장하고 실제 접속 검증은 생략
> 실무 연결: 접속 실패 시 자동 재생성하여 수업 중 장애 대응 시간을 단축합니다.

## 1. 사전 준비

### 1-1. 패키지 설치

```powershell
python -m pip install -r requirements.txt
```

### 1-2. 환경변수 준비

`.env.example`를 참고해 `.env`를 구성합니다.

필수:

- RUNPOD_API_KEY (dry-run이 아닌 실제 작업에서 필수)

주요 옵션:

- RUNPOD_GPU_TYPE
- RUNPOD_GPU_TYPE_FALLBACKS (쉼표 또는 세미콜론 구분)
- RUNPOD_TEMPLATE_ID (선택. 값이 있으면 Pod 생성 요청에 template_id를 함께 전달)
- RUNPOD_JUPYTER_CHECK_TIMEOUT

권장 기본값:

- RUNPOD_GPU_TYPE=NVIDIA A100 80GB PCIe
- RUNPOD_GPU_TYPE_FALLBACKS=NVIDIA A100-SXM4-80GB
- RUNPOD_TEMPLATE_ID= (빈 값이면 템플릿 미사용)

우선순위:

- CLI 인수(`--gpu-type`, `--gpu-type-fallback`)를 입력하면 환경변수보다 우선 적용됩니다.
- CLI에서 `--gpu-type-fallback`를 생략하면 `RUNPOD_GPU_TYPE_FALLBACKS`를 사용합니다.

기본 운영 GPU 정책(권장):

- 기본 GPU: NVIDIA A100 80GB PCIe
- 대안 GPU: NVIDIA A100-SXM4-80GB

빠른 설정 예시(.env):

```dotenv
RUNPOD_GPU_TYPE=NVIDIA A100 80GB PCIe
RUNPOD_GPU_TYPE_FALLBACKS=NVIDIA A100-SXM4-80GB
```

CLI로 일시 변경(해당 실행 1회만 적용):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"

python main.py --input "runpod-urls.xlsx" --action provision --gpu-type "NVIDIA A40"
```

### 1-4. 바로 실행하기(복붙용)

기본값(.env) 그대로 시뮬레이션:

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --dry-run
```

기본값(.env) 그대로 실제 생성(접속 체크 생략, 빠름):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision
```

Pod 생성 후 접속 상태 일괄 확인:

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

`sync --all`은 터미널에 현재 상태를 표로 출력합니다.
예: `OK`, `UNREACHABLE`, `POD_NOT_FOUND`
`UNREACHABLE`이면 상세 코드도 함께 표시됩니다. 예: `HTTP_404`

정밀 모드(접속 체크 + 자동 재생성 포함, 느림):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --jupyter-check --recreate-on-unreachable
```

### 1-3. 입력 엑셀 형식

- 시트명: 시트1
- 필수 입력 컬럼: 번호, 아이디
- 자동/운영 컬럼: 이름, RunPod URL, JupyterLab 접속 가능 상태, GPU Type, SSH
- 데이터 시작: 2행
- 강사 행: 번호 0, 아이디 instructor

참고:

- 번호 0행에 아이디/이름이 비어 있으면 자동으로 instructor로 보정됩니다.
- 이름, RunPod URL, JupyterLab 접속 가능 상태, GPU Type, SSH 컬럼이 없으면 자동 생성됩니다.

## 2. 운영 시작 전: GPU TYPE 조사

먼저 현재 계정에서 사용 가능한 GPU 타입을 확인합니다.

```powershell
python main.py --input "runpod-urls.xlsx" --list-gpu-types
```

출력 기준:

- 메모리 40GB 이상 GPU 타입만 표시
- `GPU_TYPE | 메모리GB | securePrice` 형식으로 출력

운영 팁:

- 기본 GPU 타입과 폴백 GPU 타입 1~2개를 미리 정해두세요.
- 예: A100 80GB PCIe를 기본으로 두고 A100-SXM4-80GB를 폴백으로 설정

## 3. 수업 전 생성/검증 (Provision)

### 4-1. 먼저 dry-run으로 시뮬레이션

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --dry-run --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

### 4-2. 실제 생성 실행

기본 실행(접속 체크 생략, 빠름):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

실행 시 도구가 자동으로 수행하는 것(기본):

1. 기존 Pod 조회
2. 상태가 `UNREACHABLE`, `POD_NOT_FOUND`, `TERMINATED` 중 하나면 새 Pod 생성/재생성
3. URL 생성
4. 상태 컬럼에 `CHECK_SKIPPED` 기록 (접속 체크 생략)

단순 운영 규칙:

- URL 컬럼은 유지합니다.
- `provision` 실행 시 `UNREACHABLE`, `POD_NOT_FOUND`, `TERMINATED` 상태인 행만 새 Pod를 만들고 URL/상태/GPU를 다시 저장합니다.
- `STOPPED` 상태는 자동 재생성하지 않습니다. 이 경우 `provision --recreate-if-unhealthy --overwrite-url` 또는 대상 지정 재생성 명령을 사용합니다.
- `--jupyter-check --recreate-on-unreachable` 사용 시 첫 접속 체크가 `HTTP_404`이면 현재 GPU 대신 `--gpu-type-fallback` 후보를 먼저 시도합니다.

정밀 모드(접속 체크 + 자동 재생성 포함, 느림):

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB" --jupyter-check --recreate-on-unreachable
```

정밀 모드 추가 단계:

4. JupyterLab 실제 접속 확인 (`--jupyter-check`)
5. 접속 불가면 Pod terminate 후 재생성 1회 재시도 (`--recreate-on-unreachable`)
	`HTTP_404`이고 fallback GPU가 설정돼 있으면 대체 GPU를 먼저 시도
6. RunPod URL + 접속 가능 상태 + SSH 명령을 결과 파일에 저장

### 4-3. 생성 후 JupyterLab 접속 상태 업데이트

기본 모드로 생성하면 상태 컬럼이 `CHECK_SKIPPED`로 기록됩니다.
Pod가 모두 준비된 뒤 아래 명령으로 접속 상태를 일괄 업데이트할 수 있습니다.

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

sync 결과:

- Pod가 정상 실행 중이고 JupyterLab이 응답하면 → `OK`
- URL은 있지만 JupyterLab이 응답하지 않으면 → `UNREACHABLE`
- RunPod에서 Pod가 사라진 경우 → 상태만 `POD_NOT_FOUND`
- 터미널에 `번호 / 아이디 / 상태 / URL` 표가 출력됩니다.
- `UNREACHABLE`이면 원인 확인용 상세 코드도 함께 출력됩니다. 예: `HTTP_404`, `HTTP_401`, `REQUEST_ERROR:ConnectionError`
- sync는 `JupyterLab 접속 가능 상태`를 갱신하고, Pod 메타데이터로 만들 수 있는 경우 `SSH` 명령도 함께 갱신합니다. (RunPod URL, GPU Type은 유지)

운영 팁:

- `sync`는 상태 확인/저장 전용입니다. 자동 재생성은 하지 않습니다.
- 같은 행이 반복해서 `UNREACHABLE (HTTP_404)`이면 `provision --jupyter-check --recreate-on-unreachable --gpu-type-fallback ...`으로 재시도하세요.
- RunPod 문서 기준으로 stop 이후에는 container disk가 지워질 수 있습니다. terminate 후 새 Pod를 만들면 network volume이 아닌 일반 volume disk와 Pod URL은 이어지지 않습니다.

sync는 항상 JupyterLab HTTP 체크를 수행합니다.

결과 저장 방식:

- 기본값은 입력 파일(runpod-urls.xlsx) 덮어쓰기입니다.
- 필요하면 `--output "별도파일.xlsx"`로 분리 저장할 수 있습니다.

## 4. 수업 중 운영

### 5-1. 쉬는 시간/점심시간: 전체 중지

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --all
```

### 4-2. 부분 운영 (개별/번호/아이디)

번호 기반 부분 stop:

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --numbers 3 7
```

정지한 Pod를 다시 사용해야 하면 재생성 명령을 사용합니다.

## 5. 장애 대응

### 6-1. 특정 Pod 강제 재생성

번호 기준:

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate 3 7 --overwrite-url
```

아이디 기준:

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate-ids user01 user02 --overwrite-url
```

### 6-2. 비정상 상태 자동 재생성

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate-if-unhealthy --overwrite-url
```

## 6. RunPod 웹 수동 변경 반영 (sync)

운영 중 웹에서 Pod를 급히 삭제/변경했다면 반드시 sync를 실행합니다.

전체 sync:

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

부분 sync:

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --numbers 1 2 3
```

sync 결과:

- Pod가 없으면 상태를 POD_NOT_FOUND로 기록
- URL이 있으면 접속 상태를 재평가해 상태 컬럼만 갱신
- RunPod URL, GPU Type 컬럼은 유지
- SSH 컬럼은 Pod 메타데이터에서 생성 가능한 값으로 갱신

## 7. 수업 종료 시나리오

### 8-1. 즉시 종료(비용 절감): 전체 stop

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --all
```

### 8-2. 완전 종료(리소스 정리): 전체 terminate

```powershell
python main.py --input "runpod-urls.xlsx" --action terminate --all
```

주의:

- terminate는 복구 불가 삭제입니다.
- 전체 terminate 후에는 sync를 실행해 엑셀 상태를 최종 반영하는 것을 권장합니다.

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

## 8. 운영 시나리오별 빠른 선택표

상황에 맞는 열을 골라 명령을 바로 복붙하세요.

| 항목 | ⚡ 기본 (빠른 모드) | 🟢 정밀 모드 (opt-in) | 🔧 장애 복구 |
|------|-------------------|----------------------|------------|
| **목적** | Pod 생성만 빠르게 완료 | 생성 직후 접속 검증까지 완료 | 비정상 Pod 재생성 |
| **Pod 생성** | `provision` | `provision --jupyter-check --recreate-on-unreachable` | `provision --recreate-if-unhealthy --overwrite-url` |
| **접속 체크** | 생략 (`CHECK_SKIPPED` 기록) | 자동 (HTTP 실시간 검증) | 재생성 후 자동 검증 |
| **실패 시** | 재생성 없이 `CHECK_SKIPPED` 기록 | 자동 재생성 1회 시도 | 개별 재생성 후 상태 갱신 |
| **소요 시간** | 빠름 (Pod당 5~15초) | 느림 (Pod당 30초~2분) | 중간 (대상 Pod만 처리) |
| **권장 상황** | 항상 (기본값) | 생성 직후 바로 확인 필요할 때 | 특정 학생 Pod 장애 시 |
| **상태 확인** | `sync --all` 별도 실행 | 생성과 동시에 확인됨 | sync 별도 실행 |
| **중지** | `stop --all` | `stop --all` | `stop --numbers 3 7` |
| **재개** | `provision --recreate-if-unhealthy --overwrite-url` | `provision --jupyter-check --recreate-on-unreachable` | `provision --recreate 3 7 --overwrite-url` |
| **종료** | `terminate --all` → `sync --all` | `terminate --all` → `sync --all` | (개별 terminate 후 sync) |

### 시나리오별 전체 명령 예시

**⚡ 기본 (빠른 모드)**

```powershell
# 1. 시뮬레이션
python main.py --input "runpod-urls.xlsx" --action provision --dry-run
# 2. 실제 생성 (접속 체크 생략)
python main.py --input "runpod-urls.xlsx" --action provision
# 3. 접속 상태 일괄 확인
python main.py --input "runpod-urls.xlsx" --action sync --all
# 4. 중지
python main.py --input "runpod-urls.xlsx" --action stop --all
# 5. 종료
python main.py --input "runpod-urls.xlsx" --action terminate --all
python main.py --input "runpod-urls.xlsx" --action sync --all
```

**🟢 정밀 모드 (opt-in)**

```powershell
# 1. 시뮬레이션
python main.py --input "runpod-urls.xlsx" --action provision --dry-run
# 2. 실제 생성 + 접속 검증 + 자동 재생성
python main.py --input "runpod-urls.xlsx" --action provision --jupyter-check --recreate-on-unreachable
# 3. 중지/종료는 동일
```

**🔧 장애 복구**

```powershell
# 비정상 Pod 자동 재생성
python main.py --input "runpod-urls.xlsx" --action provision --recreate-if-unhealthy --overwrite-url
# 특정 번호만 재생성
python main.py --input "runpod-urls.xlsx" --action provision --recreate 3 7 --overwrite-url
# 특정 아이디만 재생성
python main.py --input "runpod-urls.xlsx" --action provision --recreate-ids user01 user02 --overwrite-url
# 웹 수동 변경 반영
python main.py --input "runpod-urls.xlsx" --action sync --all
```

## 9. 운영 체크리스트

수업 시작 전:

1. list-gpu-types 실행
2. provision dry-run
3. provision 실제 실행
4. updates 파일의 URL/상태 컬럼 확인

수업 중:

1. break: stop --all
2. 장애 시 recreate 또는 provision + recreate-if-unhealthy

수업 종료:

1. stop --all 또는 terminate --all
2. sync --all
3. 결과 파일 보관

## 10. 테스트

```powershell
pytest -q
```


