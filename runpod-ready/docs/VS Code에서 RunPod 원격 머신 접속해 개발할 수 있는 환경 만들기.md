이 문서는 **학생들이 최종적으로 VS Code Tunnel을 사용해 RunPod 원격 머신에서 개발하는 것**을 목표로, SSH는 **초기 접속·비상 접속·터널 부팅용**으로 활용하는 방식으로 정리한 **가이드**로 RunPod 공식 문서, VS Code 공식 문서, uv 공식 문서를 기준으로 작성했습니다.

---

# VS Code에서 RunPod 원격 머신 접속해 개발할 수 있는 환경 만들기

## Windows 11 + PowerShell + uv + Python + VS Code + RunPod

## 최종 접속 방식: VS Code Tunnel

---

## 0. 최종 목표

이 가이드를 끝까지 따라하면 다음 상태가 완성됩니다.

* 로컬 Windows 11에서 `ssh-keygen`으로 SSH 키를 만들고, 학생 식별이 가능한 이메일을 주석(`-C`)으로 남깁니다.
* RunPod 계정에 공개키를 등록합니다.
* PowerShell에서 `ssh runpod-svr` 또는 본인이 정한 Host 별칭으로 RunPod에 접속할 수 있습니다.
* RunPod 원격 머신 안에 **VS Code CLI**를 설치하고 `code tunnel`을 실행합니다.
* 로컬 VS Code에서 **Tunnel로 접속**합니다.
* 원격 작업 폴더를 `/workspace`로 통일합니다.
* 로컬/원격 모두에서 `uv` 기반 Python 3.12 + `.venv` 가상환경을 맞춥니다.
* 원격 VS Code에 Python, Jupyter 같은 확장을 설치하고 GPU/Jupyter까지 점검합니다.
  RunPod은 Pod의 Connect 화면에서 SSH 명령을 제공하고, VS Code는 Remote Tunnels 방식으로 원격 머신에 접속할 수 있도록 공식적으로 지원합니다. uv는 Windows PowerShell 설치 스크립트, Linux 설치 스크립트, `uv python install 3.12`, `uv venv` 같은 흐름을 공식 문서에서 안내합니다. ([Runpod Documentation][2])

---

## 1. 준비물

### 로컬 PC

* Windows 11
* PowerShell
* VS Code 최신 버전
* OpenSSH 클라이언트 사용 가능 상태

### 계정

* RunPod 계정
* GitHub 계정

  VS Code Tunnel은 GitHub 로그인 흐름을 사용해 원격 머신 소유자 인증을 진행할 수 있고, VS Code 공식 문서도 GitHub 인증을 기준으로 설명합니다. Remote-SSH를 사용할 경우에는 OpenSSH 호환 SSH 클라이언트와 VS Code, Remote-SSH 확장이 필요합니다. ([Visual Studio Code][3])

### RunPod 쪽

* SSH 가능한 Pod
* 가능하면 공식 PyTorch 템플릿 계열 사용

  RunPod은 공식 템플릿에서 SSH가 이미 준비된 경우가 많고, VS Code/Cursor 직접 연결은 템플릿이 **SSH over exposed TCP**를 지원해야 한다고 설명합니다. 또한 `/workspace`를 대표 작업 폴더로 안내합니다. ([Runpod Documentation][2])

---

## 2. 로컬 PC에서 SSH 키 생성 (`-C "학생 식별 이메일"`)

학생 식별이 가능한 이메일을 남기는 이유는 공개키를 여러 개 운영할 때 **누구 키인지 관리하기 쉽기 때문**입니다. RunPod 문서도 SSH 키 생성 예시에서 `-C "YOUR_EMAIL@DOMAIN.COM"` 형식을 사용합니다. ([Runpod Documentation][4])

PowerShell에서 실행합니다.

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\id_ed25519 -C "student01@example.com"
```

설명:

* `-t ed25519`: 현대적인 SSH 키 알고리즘입니다.
* `-f`: 저장 경로를 지정합니다.
* `-C`: 키 식별용 주석입니다.
  RunPod 공식 가이드는 `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -C "YOUR_EMAIL@DOMAIN.COM"` 예시를 제시합니다. ([Runpod Documentation][4])

생성 결과:

* 개인키: `C:\Users\<사용자>\.ssh\id_ed25519`
* 공개키: `C:\Users\<사용자>\.ssh\id_ed25519.pub`

확인 명령:

```powershell
Get-ChildItem $HOME\.ssh
```

---

## 3. 공개키 확인 및 등록

### 3-1. 공개키 확인

```powershell
Get-Content $HOME\.ssh\id_ed25519.pub
```

또는

```powershell
cat $HOME\.ssh\id_ed25519.pub
```

출력된 한 줄 전체를 복사합니다. RunPod 문서도 `cat ~/.ssh/id_ed25519.pub`로 공개키를 확인한 뒤 계정 설정의 SSH Public Keys 필드에 넣으라고 안내합니다. ([Runpod Documentation][4])

### 3-2. RunPod 웹 사이트에서 공개키 등록

RunPod 웹 사이트 UI 흐름은 다음과 같습니다.

* 왼쪽 **Account / Settings** 메뉴
* **Settings** 화면
* **Connections** 섹션
* **SSH public keys**
* 공개키 붙여넣기
* **Update public key** 클릭

RunPod 공식 문서는 **Runpod user account settings의 SSH Public Keys 필드에 공개키를 넣으라**고 설명합니다.([Runpod Documentation][1])

### 매우 중요한 주의사항

공개키를 **Pod 시작 전에** RunPod 계정 설정에 넣어두면, RunPod이 Pod 시작 시 `~/.ssh/authorized_keys`에 자동 주입합니다. 하지만 **Pod가 이미 실행 중인 뒤에 키를 등록하면 자동 주입이 일어나지 않습니다.** 이 경우에는:

* Pod를 종료 후 다시 배포하거나
* 실행 중인 Pod의 Web Terminal에 들어가서 직접 `authorized_keys`를 수정해야 합니다. ([Runpod Documentation][4])

이 부분은 학생들이 가장 많이 막히는 지점입니다.
즉, **SSH 키 등록 → 그 다음 Pod 시작** 순서를 강하게 권장합니다. ([Runpod Documentation][4])

---

## 4. `.ssh\config` 파일 작성

여기서 가장 중요한 학습 포인트는, **RunPod의 최신 SSH 정보는 “IP를 찾아서 수동 입력”하는 것보다 Pod의 Connect 화면에 표시되는 SSH 명령을 보고 분해해서 쓰는 것이 정확하다**는 점입니다. RunPod 공식 문서는 Pod의 **Connect 탭**에서 SSH 명령을 복사하라고 설명합니다. ([Runpod Documentation][2])

### 4-1. RunPod에서 SSH 명령 확인 위치

1. RunPod 콘솔에서 **Pods**로 이동합니다.
2. 접속할 Pod를 클릭합니다.
3. **Connect**를 엽니다.
4. **SSH** 영역을 확인합니다.
   RunPod의 기본 SSH 가이드는 Pod의 Connect 탭에 있는 SSH 명령을 복사하라고 설명합니다. VS Code/Cursor 직접 연결 가이드는 같은 Connect 화면에서 **SSH over exposed TCP** 명령을 복사하라고 설명합니다. ([Runpod Documentation][2])

### 4-2. 최신 예시

RunPod 화면에 다음과 같은 명령이 보일 겁니니다.

```bash
ssh ufzqm4cridlzsm-6441206f@ssh.runpod.io -i ~/.ssh/id_ed25519
```

이 한 줄을 다음처럼 읽으면 됩니다.

* `HostName` = `ssh.runpod.io`
* `User` = `ufzqm4cridlzsm-6441206f`
* `IdentityFile` = `~/.ssh/id_ed25519`

그래서 `.ssh\config`에는 이렇게 씁니다.

```ssh
Host runpod-svr
    HostName ssh.runpod.io
    User ufzqm4cridlzsm-6441206f
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
    ServerAliveCountMax 120
```

RunPod 공식 SSH 가이드는 Connect 탭의 기본 SSH 명령 예시를 `ssh <사용자>@ssh.runpod.io -i ~/.ssh/id_ed25519` 형태로 제시합니다. ([Runpod Documentation][2])

### 4-3. 왜 `<RunPod_IP>`라고만 쓰면 안 되는가

RunPod 공식 문서를 보면 접속 방식이 두 가지이기 때문입니다.

1. **기본 SSH**
   `ssh <사용자>@ssh.runpod.io -i ~/.ssh/id_ed25519` 형태 ([Runpod Documentation][2])

2. **SSH over exposed TCP**
   `ssh root@<공인IP> -p <포트> -i ~/.ssh/id_ed25519` 형태
   VS Code / Cursor의 Remote-SSH 직접 연결 설명은 이 방식을 기준으로 되어 있습니다. ([Runpod Documentation][2])

따라서 학생용 문서에서는 `<RunPod_IP>` 하나를 적는 대신,
**“Connect 화면의 SSH 명령을 보고 HostName, User, Port를 분해해 넣는다”**라고 설명하는 것이 실제 UI와 맞습니다. ([Runpod Documentation][2])

### 4-4. `.ssh\config` 파일 여는 방법

```powershell
notepad $HOME\.ssh\config
```

처음이면 파일이 없을 수 있습니다. 그 경우 새로 저장하면 됩니다.

### 4-5. 수업용 권장 config

이번 문서의 최종 목표는 **학생들이 VS Code Tunnel을 쓰는 것**이므로, 일단은 기본 SSH 별칭 하나면 충분합니다.

```ssh
Host runpod-svr
    HostName ssh.runpod.io
    User <RunPod Connect 화면에 표시된 사용자명>
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
    ServerAliveCountMax 120
```

설명:

* `ServerAliveInterval 30`: 30초마다 keepalive를 보냅니다.
* `ServerAliveCountMax 120`: 일시적인 네트워크 흔들림에 더 강해집니다.
  이 두 값은 OpenSSH 일반 설정이며, 교육 환경에서 세션이 끊기는 문제를 줄이는 데 실무적으로 자주 씁니다.

---

## 5. 로컬 PowerShell에서 SSH 접속 테스트

이제 PowerShell에서 테스트합니다.

```powershell
ssh runpod-svr
```

정상이라면 질문에 주신 것처럼 RunPod 배너와 함께 쉘 프롬프트가 뜹니다.

```bash
root@xxxxxxxx:/#
```

RunPod 공식 문서상 SSH는 장시간 작업과 개발용으로 권장되는 접속 방식이고, Web terminal은 빠른 접근용이며 장시간 작업에는 권장되지 않습니다. 즉, 학생들이 처음 환경을 붙일 때는 **SSH로 먼저 들어가 보는 것**이 맞습니다. ([Runpod Documentation][5])

### 접속이 안 되면 가장 먼저 확인할 것

1. 공개키를 계정에 등록했는가
2. 그 키를 등록한 뒤 Pod를 새로 시작했는가
3. Connect 화면의 사용자명을 제대로 config에 넣었는가
   키를 Pod 실행 후에 등록했다면 자동 주입이 안 될 수 있다는 점이 핵심입니다. ([Runpod Documentation][4])

---

## 6. 로컬 VS Code에 필요한 확장 설치

학생들이 최종적으로 사용할 것은 **VS Code Tunnel**이지만, 교육적으로는 SSH와 Tunnel의 차이를 이해시키는 것이 좋습니다.
로컬 VS Code에는 다음 확장을 설치해 두는 것을 권장합니다.

* Remote - SSH
* Remote - Tunnels
* Python
* Jupyter

VS Code 공식 문서는 Remote-SSH 사용 시 Remote-SSH 확장이 필요하다고 설명합니다. Tunnel 쪽은 VS Code Server / Remote Tunnels 구조를 사용하며, 로컬 VS Code에서 Remote Tunnels 기능을 통해 연결할 수 있습니다. Python 개발에는 Python 확장, 노트북에는 Jupyter 확장이 필요합니다. ([Visual Studio Code][6])

### 왜 Remote-SSH도 설치하나요?

이번 수업의 **최종 사용 방식은 Tunnel**이지만, 학생들이 다음을 이해하기 좋습니다.

* SSH는 서버에 “직접” 붙는 방식
* Tunnel은 GitHub 로그인 기반으로 VS Code Server에 “중계” 연결하는 방식

또한 Tunnel 문제 발생 시 SSH로 들어가서 복구할 수 있어야 하기 때문입니다. VS Code 공식 문서도 SSH와 Tunnels를 모두 원격 개발 방식으로 안내합니다. ([Visual Studio Code][6])

---

## 7. RunPod 안에 VS Code CLI 설치

이제 SSH로 들어간 RunPod 원격 쉘에서 작업합니다.

아래의 명령을 실행합니다.

```bash
curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output vscode_cli.tar.gz
tar -xf vscode_cli.tar.gz
```

VS Code 공식 Remote Tunnels 문서도 **standalone / terminal install** 방식에서 tar 파일을 받아 압축 해제한 뒤 `./code tunnel`을 사용하는 흐름을 설명합니다. 또한 이 방식에서는 명령이 `code`가 아니라 `./code`로 시작할 수 있다고 명시합니다. ([Visual Studio Code][3])

### 왜 `cli-alpine-x64`를 쓰나요?

RunPod 템플릿에 따라 베이스 이미지가 경량 Linux 계열일 수 있어서, 질문에서 실제로 성공한 현재 절차를 수업 문서의 기본 경로로 쓰는 것이 안전합니다. 다만 템플릿이 바뀌면 CLI 다운로드 대상도 달라질 수 있으므로, VS Code 공식 다운로드 문서의 CLI 배포 방식을 우선 기준으로 삼는 것이 좋습니다. ([Visual Studio Code][3])

### 설치 확인

압축 해제 후 현재 폴더에 `code` 실행 파일이 생겼는지 확인합니다.

```bash
ls -l
```

---

## 8. RunPod에서 VS Code Tunnel 실행

아래의 명령을 실행합니다.

```bash
./code tunnel --accept-server-license-terms
```

VS Code 공식 문서는:

* `code tunnel` 명령이 원격 머신에 VS Code Server를 다운로드/시작하고
* 해당 머신에 대한 터널을 생성하며
* 처음 실행 시 라이선스 동의가 필요하고
* `--accept-server-license-terms` 옵션으로 프롬프트를 생략할 수 있다고 설명합니다. ([Visual Studio Code][3])

### 실행 중 보게 되는 흐름

질문에서 주신 실제 출력처럼 보통 다음 순서로 진행됩니다.

1. 라이선스 안내 출력
2. 로그인 방식 선택
   `GitHub Account`
3. GitHub device login 코드 표시
4. 머신 이름 지정
   예: `instructor`
5. 터널 생성
6. `https://vscode.dev/tunnel/<머신이름>` 링크 출력
7. VS Code Server 다운로드 및 시작

이 전체 흐름은 VS Code 공식 문서의 Tunnel 설명과 일치합니다. 공식 문서도 CLI가 `vscode.dev/tunnel/<machine_name>` 형태의 URL을 출력한다고 설명합니다. ([Visual Studio Code][3])

### 수업용 머신 이름 권장

학생은 다음처럼 지정하면 관리가 쉽습니다.

* `student-01`
* `student-02`
* `instructor`

머신 이름은 GitHub로 인증된 동일 사용자 계정 아래에서 식별자로 쓰이므로, 수업 운영상 사람이 알아보기 쉽게 정하는 것이 좋습니다. VS Code 공식 문서도 원격 머신 이름 기반 tunnel URL을 설명합니다. ([Visual Studio Code][3])

---

## 9. 로컬 VS Code에서 Tunnel 로그인

학생들이 최종적으로 실제 사용할 방식은 여기입니다.

### 방법 1: VS Code 앱에서 접속

1. 로컬 VS Code 실행
2. 커맨드 팔레트(CTRL + SHIFT + P) 열기
3. **Connect to Tunnel** 또는 Remote Tunnels 관련 명령 실행
4. GitHub 로그인
5. 방금 원격에서 만든 머신 선택

VS Code 공식 문서는 로컬 클라이언트가 처음으로 해당 tunnel URL 또는 tunnel 머신에 접근할 때 GitHub 인증을 요구한다고 설명합니다. ([Visual Studio Code][3])

### 방법 2: 브라우저 경유

질문에서 실제 출력된 링크 예시:

```text
https://vscode.dev/tunnel/instructor
```

이 링크를 브라우저에서 열어 접속할 수도 있습니다. VS Code 공식 문서도 CLI가 이런 형태의 `vscode.dev` URL을 출력한다고 설명합니다. ([Visual Studio Code][3])

### 교육적으로 왜 Tunnel을 최종 방식으로 쓰나요?

VS Code Server 문서는 Tunnel의 장점으로:

* SSH가 제한적인 환경
* 웹 기반 접속 필요
* 태블릿/iPad 같은 기기에서도 사용 가능
  같은 시나리오를 제시합니다. 학교·교육센터 환경처럼 네트워크 제약이 있는 곳에서 특히 유리합니다. ([Visual Studio Code][7])

---

## 10. 연결 성공 후, 원격 VS Code 상태 확인

Tunnel로 접속되면 새 VS Code 창 또는 웹 에디터가 열리고, 원격 머신에 붙은 상태가 됩니다.

### 확인 1: 터미널 열기

원격 터미널에서:

```bash
hostname
pwd
whoami
```

* `hostname`: 내가 연결된 컨테이너/머신 확인
* `pwd`: 현재 작업 위치 확인
* `whoami`: 현재 사용자 확인

### 확인 2: VS Code Server 상태

실제 로그에 `Server started`가 떴다면 정상입니다. VS Code 공식 문서도 `code tunnel`이 VS Code Server를 다운로드하고 시작한다고 설명합니다. ([Visual Studio Code][3])

### 확인 3: 원격 연결 표시

좌측 하단의 원격 연결 표시나 제목 표시줄에 원격 머신명이 보이면 정상입니다. VS Code는 Remote Explorer와 원격 연결 UI를 제공한다고 안내합니다. ([Visual Studio Code][3])

---

## 11. 원격 VS Code에 필요한 확장 설치

여기서 중요한 학습 포인트는 **“로컬 확장”과 “원격 확장”이 다를 수 있다**는 점입니다.
원격 개발에서는 Python, Jupyter 같은 확장이 **원격 호스트 쪽에 설치**되어야 제대로 동작합니다. VS Code Remote-SSH 문서는 원격 호스트에서 사용할 확장을 자동 설치하거나 기본 설치 목록을 지정하는 기능을 설명합니다. ([Visual Studio Code][6])

권장 설치:

* Python
* Pylance
* Jupyter

### 왜 원격에 설치해야 하나요?

학생이 실제 실행하는 Python, kernel, notebook은 **RunPod 원격 머신**에서 돌아가기 때문입니다. Python 확장은 현재 선택한 인터프리터 기준으로 실행되고, Jupyter 문서는 활성화한 Python 환경에 Jupyter 패키지가 있어야 노트북 실행이 가능하다고 설명합니다. ([Visual Studio Code][8])

### 설치 시 인터넷 조건

VS Code Remote FAQ는 원격 확장 설치를 위해 보통 `marketplace.visualstudio.com` 등으로의 HTTPS(443) 아웃바운드 연결이 필요하다고 설명합니다. 학교망에서 막히면 이 부분이 원인일 수 있습니다. ([Visual Studio Code][9])

---

## 12. 원격 작업 폴더를 `/workspace` 로 바꾸기

RunPod의 VS Code/Cursor 연결 가이드는 원격 접속 후 보통 `/workspace` 폴더를 열라고 안내합니다. ([Runpod Documentation][4])

원격 터미널에서:

```bash
cd /workspace
pwd
```

VS Code 메뉴에서는:

* File
* Open Folder
* `/workspace`

### 왜 `/workspace`를 통일하나요?

교육에서는 학생마다 경로가 다르면 설명이 꼬입니다.
또 RunPod 문서도 `/workspace`를 대표 작업 위치로 안내하므로, 실습 폴더 기준을 `/workspace`로 통일하는 것이 가장 안정적입니다. ([Runpod Documentation][4])

---

## 13. `/workspace` 에서 작업 구조 만들기

예시:

```bash
cd /workspace
mkdir -p class/runpod_tunnel_lab
cd class/runpod_tunnel_lab
mkdir -p d01 d02 notebooks src data
pwd
```

권장 구조:

```text
/workspace/class/runpod_tunnel_lab
├─ d01
├─ d02
├─ notebooks
├─ src
└─ data
```

### 학습 포인트

* `/workspace`는 “공용 기준 경로”
* 그 아래 프로젝트 폴더는 “수업 단위”
* 그 아래 `d01`, `d02`는 “교시/일차 단위”
  이렇게 계층을 분리하면 실습 안내가 쉬워집니다.

---

## 14. Python 인터프리터 선택

이번 가이드의 요구사항은 **로컬/원격 동일하게 uv로 Python 3.12 + venv**를 쓰는 것입니다.
uv는 Windows PowerShell 설치 스크립트와 Linux 설치 스크립트를 제공하며, `uv python install 3.12`, `uv venv`로 Python 버전 설치와 가상환경 생성을 공식 지원합니다. ([Astral Docs][10])

### 14-1. 로컬 Windows에 uv 설치

PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

uv 공식 문서의 Windows 설치 방법입니다. ([Astral Docs][10])

### 14-2. 원격 Linux(RunPod)에 uv 설치

RunPod 원격 터미널:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

uv 공식 문서의 Linux/macOS 설치 방법입니다. ([Astral Docs][10])

설치 후 shell 반영이 필요하면 새 터미널을 열거나 안내 메시지를 따릅니다.

### 14-3. Python 3.12 설치

로컬/원격 모두 동일:

```bash
uv python install 3.12
```

uv는 `uv python install 3.12`로 최신 3.12 패치 버전을 설치할 수 있다고 설명합니다. 설치된 Python 실행 파일은 PATH에 추가될 수 있으며, 필요하면 `uv python update-shell`로 shell 경로를 반영할 수 있습니다. ([Astral Docs][11])

### 14-4. 가상환경 생성

프로젝트 루트에서:

```bash
uv venv --python 3.12 .venv
```

또는 이미 `3.12`가 준비되어 있다면:

```bash
uv venv .venv
```

uv는 필요 시 Python을 자동 다운로드할 수 있고, `uv venv --python 3.12` 같은 방식으로 특정 버전 기반 환경을 만들 수 있습니다. ([Astral Docs][12])

### 14-5. 활성화

#### Windows PowerShell

```powershell
. .\.venv\Scripts\Activate.ps1
```

#### Linux / RunPod

```bash
source .venv/bin/activate
```

### 14-6. VS Code에서 인터프리터 선택

Command Palette에서:

```text
Python: Select Interpreter
```

그리고 `.venv`를 선택합니다. VS Code Python 공식 문서는 Python: Select Interpreter 명령으로 인터프리터를 고르라고 설명합니다. ([Visual Studio Code][8])

---

## 15. GPU 및 Python 동작 확인

### Python 확인

```bash
python --version
which python
```

또는 Windows에서는:

```powershell
python --version
Get-Command python
```

### 간단한 Python 실행

```bash
python -c "print('hello from runpod')"
```

### GPU 확인

```bash
nvidia-smi
```

RunPod은 GPU Pod 환경이므로, 여기서 GPU 이름과 메모리가 보이면 정상입니다.

### PyTorch가 이미 있거나 설치 후 확인할 때

```python
import torch
print(torch.__version__)
print(torch.cuda.is_available())
if torch.cuda.is_available():
    print(torch.cuda.get_device_name(0))
```

### 학습 포인트

* SSH/Tunnel 연결 성공 ≠ Python 환경 완료
* Python 환경 완료 ≠ GPU 라이브러리 확인 완료
  따라서 반드시 세 단계를 각각 점검해야 합니다.

---

## 16. Jupyter Notebook 동작 확인

VS Code Jupyter 문서는, Jupyter Notebook을 사용하려면 **활성화한 Python 환경 안에 `jupyter` 패키지**가 있어야 하고, 먼저 적절한 인터프리터를 선택해야 한다고 설명합니다. ([Visual Studio Code][13])

원격 `.venv` 활성화 후:

```bash
uv pip install jupyter ipykernel
python -m ipykernel install --user --name runpod-312 --display-name "Python 3.12 (runpod)"
```

그 다음 `/workspace` 아래에 `test.ipynb`를 만들고, 우측 상단 커널 선택에서:

* `Python 3.12 (runpod)`
  또는 해당 `.venv` 기반 인터프리터를 고릅니다.
  VS Code Jupyter 문서는 notebook 생성 후 우측 상단 kernel picker에서 커널을 선택하라고 설명합니다. ([Visual Studio Code][13])

### 가장 간단한 테스트 셀

```python
print("notebook ok")
```

### GPU 테스트 셀

```python
import torch
print(torch.cuda.is_available())
```

---

## 17. 터널 유지 및 재접속

### 핵심 원리

VS Code Tunnel은 원격 머신에서 `code tunnel` 프로세스가 살아 있어야 합니다. VS Code 공식 문서는 `code tunnel`이 해당 머신에 터널을 만들고, 그 머신 이름 또는 `vscode.dev` URL로 접속하게 된다고 설명합니다. ([Visual Studio Code][3])

### 재접속 절차

1. Pod가 살아 있는지 확인
2. SSH로 들어가 `./code tunnel`이 살아 있는지 확인
3. 필요하면 다시 실행
4. 로컬 VS Code에서 Connect to Tunnel로 다시 연결

### Pod를 껐다 켜면 주의할 점

* Tunnel은 다시 열면 되지만
* SSH 쪽은 Pod 상태에 따라 연결 정보가 바뀔 수 있습니다.
  RunPod은 특히 **SSH over exposed TCP 포트가 stop/resume 후 바뀔 수 있다**고 공식 문서에서 설명합니다. Tunnel을 주 방식으로 쓰면 학생 입장에서는 이 변화의 영향을 덜 받지만, SSH 복구용 설정은 다시 확인해야 할 수 있습니다. ([Runpod Documentation][4])

### 수업 운영 팁

학생에게는 이렇게 설명하면 됩니다.

* 평소 개발: **VS Code Tunnel**
* 문제 복구: **SSH**
* 급한 확인: **RunPod Web Terminal**
  단, Web Terminal은 장시간 작업용으로는 권장되지 않습니다. ([Runpod Documentation][5])

---

## 18. 수업용 권장 네이밍 규칙

학생들이 헷갈리지 않게 다음처럼 통일하는 것을 권장합니다.

### SSH Host 별칭

```text
runpod-student01
runpod-student02
runpod-instructor
```

### Tunnel 머신 이름

```text
student-01
student-02
instructor
```

### 프로젝트 폴더

```text
/workspace/class/ai-agent-lab
/workspace/class/llm-ft-lab
```

### 일차/교시 폴더

```text
d01
d02
p01
p02
```

### 가상환경 이름

```text
.venv
```

학습 이유:

* 문서와 화면 설명이 일치합니다.
* 조교/강사가 원격으로 봐줄 때 빠릅니다.
* 학생이 경로를 복사해 질문하기 쉽습니다.

---

## 19. 학생용 운영 체크리스트

아래를 위에서 아래 순서대로 확인하면 됩니다.

1. 로컬에서 SSH 키를 만들었다.
2. 공개키를 RunPod 계정의 **SSH Public Keys**에 넣고 저장했다.
3. 키 등록 후 Pod를 시작했다.
4. Pod의 Connect 화면에서 SSH 명령을 확인했다.
5. `.ssh\config`에 `HostName`, `User`, `IdentityFile`를 정확히 넣었다.
6. `ssh runpod-svr` 접속이 된다.
7. RunPod 안에 VS Code CLI를 다운로드했다.
8. `./code tunnel --accept-server-license-terms`를 실행했다.
9. GitHub 로그인과 머신 이름 지정을 마쳤다.
10. 로컬 VS Code에서 Connect to Tunnel로 연결했다.
11. `/workspace`를 열었다.
12. 원격에 Python / Jupyter 확장을 설치했다.
13. `uv python install 3.12`를 했다.
14. `uv venv --python 3.12 .venv`를 만들었다.
15. 인터프리터를 `.venv`로 선택했다.
16. `nvidia-smi`가 된다.
17. Notebook 셀이 실행된다.

---

## 20. 자주 막히는 문제와 해결

### 문제 1. SSH 접속 시 비밀번호를 물어본다

가장 흔한 원인은 공개키가 Pod의 `authorized_keys`에 들어가지 않은 경우입니다. RunPod은 키를 Pod 시작 전에 계정 설정에 등록하면 자동 주입하지만, Pod가 이미 실행된 뒤 키를 넣으면 자동 주입하지 않는다고 설명합니다. 이 경우 Pod를 재배포하거나 Web Terminal에서 직접 수정해야 합니다. ([Runpod Documentation][4])

### 문제 2. RunPod에서 SSH 명령은 보이는데 VS Code Remote-SSH용 공인 IP/포트 명령이 안 보인다

RunPod 공식 문서에 따르면, 어떤 템플릿은 **SSH over exposed TCP**를 지원하지 않을 수 있습니다. 이 경우 VS Code/Cursor의 Remote-SSH 직접 연결은 안 되지만, 기본 SSH 터미널 연결은 가능합니다. ([Runpod Documentation][4])

이번 가이드의 최종 방식은 Tunnel이므로, 이런 경우에도 SSH로 들어간 뒤 VS Code Tunnel을 실행하면 수업 진행은 가능합니다. 이 점이 Tunnel을 최종 방식으로 삼는 큰 장점입니다. ([Visual Studio Code][7])

### 문제 3. Tunnel 메뉴를 못 찾겠다

VS Code와 Remote Tunnels 기능이 최신 상태인지 확인하세요. VS Code 공식 문서는 Account 메뉴나 Command Palette에서 **Remote Tunnels: Turn on Remote Tunnel Access** 같은 흐름을 안내합니다. ([Visual Studio Code][3])

### 문제 4. `./code tunnel` 실행은 됐는데 접속이 안 된다

원격에서:

```bash
./code tunnel
```

을 다시 실행해 로그를 봅니다. VS Code 공식 문서는 `code tunnel`이 서버 다운로드와 시작을 수행한다고 설명하므로, 이 단계 로그가 가장 중요합니다. ([Visual Studio Code][3])

### 문제 5. 원격 확장이 설치되지 않는다

원격 확장 설치에는 VS Code Marketplace로의 HTTPS 아웃바운드 접근이 필요할 수 있습니다. 학교망이나 제한된 네트워크라면 원격 확장 설치가 멈출 수 있습니다. ([Visual Studio Code][9])

### 문제 6. Jupyter Notebook은 열리는데 셀이 실행되지 않는다

* Python 인터프리터를 `.venv`로 골랐는지
* `jupyter`, `ipykernel`이 그 환경에 설치되었는지
* kernel picker에서 올바른 커널을 선택했는지
  를 확인합니다. VS Code Jupyter 문서는 이 흐름을 공식적으로 설명합니다. ([Visual Studio Code][13])

### 문제 7. `/workspace`가 아니라 `/root`에서 작업 중이다

원격 접속 직후 현재 위치가 `/root`일 수 있습니다. RunPod 가이드는 보통 `/workspace`를 작업 폴더로 열라고 안내하므로, 반드시 `/workspace`로 이동해 수업을 진행하세요. ([Runpod Documentation][4])

---

## 21. 최종 완료 상태

다음 상태면 준비가 끝난 것입니다.

* PowerShell에서 `ssh runpod-svr`가 된다.
* RunPod 원격 안에서 `./code tunnel --accept-server-license-terms`가 성공한다.
* 로컬 VS Code에서 Tunnel 연결이 된다.
* `/workspace`가 열린다.
* 원격 Python 인터프리터가 `.venv`로 잡힌다.
* `python --version`이 3.12 계열이다.
* `nvidia-smi`가 된다.
* `.ipynb` 셀이 실행된다.
  즉, **접속 성공 → 작업 폴더 통일 → Python 환경 통일 → GPU/Jupyter 검증**까지 끝나야 “개발 가능한 상태”입니다.

---

## 22. 복붙용 핵심 명령 모음

### 22-1. 로컬 Windows PowerShell

```powershell
# SSH 키 생성
ssh-keygen -t ed25519 -f $HOME\.ssh\id_ed25519 -C "student01@example.com"

# 공개키 확인
Get-Content $HOME\.ssh\id_ed25519.pub

# SSH config 열기
notepad $HOME\.ssh\config

# SSH 접속 테스트
ssh runpod-svr

# uv 설치
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 프로젝트 폴더에서 가상환경 생성
uv python install 3.12
uv venv --python 3.12 .venv
. .\.venv\Scripts\Activate.ps1
```

### 22-2. RunPod 원격 Linux

```bash
# VS Code CLI 다운로드
curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output vscode_cli.tar.gz

# 압축 해제
tar -xf vscode_cli.tar.gz

# Tunnel 시작
./code tunnel --accept-server-license-terms

# /workspace 이동
cd /workspace

# 실습 구조 만들기
mkdir -p class/runpod_tunnel_lab
cd class/runpod_tunnel_lab
mkdir -p d01 d02 notebooks src data

# uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# Python 3.12 설치
uv python install 3.12

# venv 생성
uv venv --python 3.12 .venv

# 활성화
source .venv/bin/activate

# Jupyter 설치
uv pip install jupyter ipykernel

# 커널 등록
python -m ipykernel install --user --name runpod-312 --display-name "Python 3.12 (runpod)"

# GPU 확인
nvidia-smi
```

---

## Remote-SSH vs Tunnel 차이 + 언제 무엇을 써야 하는지

이번 수업의 결론부터 말씀드리면, **학생 최종 사용 방식은 VS Code Tunnel**로 두는 것이 가장 운영이 편합니다.

### Remote-SSH

* SSH로 원격 머신에 직접 붙는 방식입니다.
* 설정이 명확하고 빠르지만, 네트워크 제약과 포트/SSH 준비 상태에 영향을 더 받습니다.
* RunPod에서도 공식적으로 지원하지만, VS Code/Cursor 직접 연결은 템플릿이 SSH over exposed TCP를 지원해야 합니다. ([Visual Studio Code][6])

### VS Code Tunnel

* 원격 머신에서 `code tunnel`을 띄우고 GitHub 계정으로 인증해 접속합니다.
* SSH가 제한적인 환경이나 웹 기반 접근이 필요한 상황에 특히 유리합니다.
* VS Code Server 공식 문서도 SSH가 제한적인 환경, 브라우저 기반 개발, 태블릿 환경 등에서 Tunnels가 유용하다고 설명합니다. ([Visual Studio Code][7])

### 교육 현장 기준 추천

* **초기 세팅 / 복구 / 긴급 접근**: SSH
* **학생 일상 개발 / 실제 실습**: Tunnel

이렇게 두 단계를 나누면, 학생은 최종적으로 GUI 친화적인 Tunnel을 쓰고, 강사는 SSH로 문제를 빠르게 복구할 수 있습니다.

---

## 참고 자료

이 문서는 다음 공식 자료를 기준으로 구성했습니다.

* RunPod SSH 기본 접속: Pod의 Connect 탭에서 SSH 명령 복사, 계정 설정의 SSH Public Keys 사용, 키 등록 시점에 따라 자동 주입 여부 달라짐. ([Runpod Documentation][2])
* RunPod VS Code/Cursor 연결: Remote-SSH, SSH over exposed TCP, `/workspace` 열기, 포트 변경 가능성. ([Runpod Documentation][4])
* VS Code Tunnel: `code tunnel`, GitHub 인증, `vscode.dev/tunnel/<machine_name>` URL, 라이선스 동의, VS Code Server 동작 원리. ([Visual Studio Code][3])
* uv: Windows PowerShell 설치, Linux 설치, `uv python install 3.12`, `uv venv`. ([Astral Docs][10])
* VS Code Python/Jupyter: `Python: Select Interpreter`, Jupyter 환경과 kernel picker. ([Visual Studio Code][8])


[1]: https://docs.runpod.io/pods/configuration/use-ssh?utm_source=chatgpt.com "Connect to a Pod with SSH"
[2]: https://docs.runpod.io/pods/configuration/use-ssh "Connect to a Pod with SSH - Runpod Documentation"
[3]: https://code.visualstudio.com/docs/remote/tunnels "Developing with Remote Tunnels"
[4]: https://docs.runpod.io/pods/configuration/connect-to-ide "Connect to a Pod with VSCode or Cursor - Runpod Documentation"
[5]: https://docs.runpod.io/pods/connect-to-a-pod "Connection options - Runpod Documentation"
[6]: https://code.visualstudio.com/docs/remote/ssh "Remote Development using SSH"
[7]: https://code.visualstudio.com/docs/remote/vscode-server "Visual Studio Code Server"
[8]: https://code.visualstudio.com/docs/languages/python "Python in Visual Studio Code"
[9]: https://code.visualstudio.com/docs/remote/faq?utm_source=chatgpt.com "Remote Development FAQ"
[10]: https://docs.astral.sh/uv/getting-started/installation/ "Installation | uv"
[11]: https://docs.astral.sh/uv/concepts/python-versions/ "Python versions | uv"
[12]: https://docs.astral.sh/uv/?utm_source=chatgpt.com "uv - Astral Docs"
[13]: https://code.visualstudio.com/docs/datascience/jupyter-notebooks "Jupyter Notebooks in VS Code"
