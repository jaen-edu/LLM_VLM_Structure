# RunPod 교육 운영 1페이지 체크리스트

이 문서는 수업 당일 운영자가 빠르게 확인/실행할 수 있도록 최소 단계만 정리한 체크리스트입니다.

## 1. 수업 시작 전 (T-10분)

[ ] 가상환경 활성화

```powershell
& .\.venv\Scripts\Activate.ps1
```

[ ] GPU 타입 조회

```powershell
python main.py --input "runpod-urls.xlsx" --list-gpu-types
```

[ ] 생성 시뮬레이션(dry-run)

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --dry-run --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

[ ] 실제 Pod 생성

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

[ ] 접속 상태 일괄 확인(sync)

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

- 터미널에 번호/아이디/상태/URL 표가 바로 출력됨
- UNREACHABLE이면 `HTTP_404` 같은 상세 코드도 함께 표시됨

[ ] 결과 파일 확인

- runpod-urls.xlsx
- RunPod URL
- JupyterLab 접속 가능 상태
- GPU Type

## 2. 수업 중 운영

### 2-1. 쉬는 시간/점심 시간

[ ] 전체 stop

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --all
```

### 2-3. 부분 제어(개별 장애/요청)

[ ] 번호 기반 부분 stop

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --numbers 3 7
```

[ ] 중지한 Pod 재사용이 필요하면 재생성 명령 사용

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate-if-unhealthy --overwrite-url
```

## 3. 장애 대응

[ ] 특정 번호 재생성

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate 3 7 --overwrite-url
```

[ ] 특정 아이디 재생성

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --recreate-ids user01 user02 --overwrite-url
```

[ ] 웹에서 수동 조작 후 상태 동기화

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

[ ] UNREACHABLE이 반복되면 정밀 재생성

```powershell
python main.py --input "runpod-urls.xlsx" --action provision --jupyter-check --recreate-on-unreachable --gpu-type "NVIDIA A100 80GB PCIe" --gpu-type-fallback "NVIDIA A100-SXM4-80GB"
```

## 4. 수업 종료

### 4-1. 비용 절감(재사용 예정)

[ ] 전체 stop

```powershell
python main.py --input "runpod-urls.xlsx" --action stop --all
```

### 4-2. 완전 종료(전체 Pod 제거)

[ ] 전체 terminate

```powershell
python main.py --input "runpod-urls.xlsx" --action terminate --all
```

[ ] 최종 sync

```powershell
python main.py --input "runpod-urls.xlsx" --action sync --all
```

## 5. 운영 원칙

- terminate는 복구 불가 삭제이므로 stop과 구분해 사용
- 수동 변경 후에는 반드시 sync 실행
- sync는 상태 확인/저장만 수행하고, 자동 재생성은 provision에서 수행
- 접속 상태가 UNREACHABLE/POD_NOT_FOUND/TERMINATED이면 plan으로 재생성 명령 재확인
- STOPPED는 재생성(`provision --recreate-if-unhealthy --overwrite-url`)으로 복구
- UNREACHABLE이 `HTTP_404`로 반복되면 fallback GPU를 포함한 정밀 provision을 우선 사용
