# 학생용 가이드: 개인 PC에서 내가 만든 RunPod Pod에 SSH로 접속하기

## 1. 이 문서의 목적

이 문서는 학생이 **자기 개인 PC**에서 **자기가 직접 생성한 RunPod Pod 인스턴스**에 SSH로 접속하는 방법을 단계별로 설명합니다.

기준 환경은 아래와 같습니다.

- 개인 PC: Windows 11
- 원격 환경: RunPod Pod
- 접속 방식: SSH 키 기반 접속
- 선택 도구: PowerShell, VS Code Remote - SSH

이 가이드는 아래 두 가지를 모두 다룹니다.

1. PowerShell에서 먼저 SSH 접속이 되는지 확인하는 방법
2. VS Code로 같은 Pod에 편하게 다시 붙는 방법

## 2. 먼저 이해하면 쉬운 핵심 용어

SSH (Secure Shell):
- 내 PC에서 원격 리눅스 서버에 안전하게 접속하는 방식입니다.
- 반대 개념: 웹 브라우저만으로 접속하는 HTTP 기반 접속
- 왜 중요한가: 터미널 작업, 파일 전송, VS Code 원격 연결의 기본이 됩니다.
- 이번 실습 연결: RunPod Pod를 내 PC에서 직접 제어하려면 가장 먼저 익혀야 하는 접속 방법입니다.

SSH 키 (SSH Key)
- 비밀번호 대신 사용하는 로그인 열쇠 쌍입니다. 개인키와 공개키로 구성됩니다.
- 반대 개념: 매번 비밀번호를 입력하는 로그인 방식
- 왜 중요한가: RunPod는 SSH 키 기반 접속을 권장하며, VS Code 연결도 이 방식이 가장 안정적입니다.
- 이번 실습 연결: 내 공개키를 RunPod 계정이나 Pod에 등록해야 내 PC에서 접속할 수 있습니다.

공개키 (Public Key)
- 다른 곳에 등록해도 되는 키입니다.
- 반대 개념: 절대 공유하면 안 되는 개인키(Private Key)
- 왜 중요한가: 공개키가 Pod의 `authorized_keys`에 들어 있어야 SSH 접속이 허용됩니다.
- 이번 실습 연결: RunPod 계정의 `SSH Public Keys`에 붙여 넣는 값이 바로 이 공개키입니다.

SSH over exposed TCP
- RunPod Pod의 SSH 포트를 공인 IP와 외부 포트로 연결해 주는 방식입니다.
- 반대 개념: RunPod 내부 프록시를 거치는 Basic SSH
- 왜 중요한가: VS Code Remote - SSH와 일반 SSH 클라이언트에서 가장 익숙하게 사용할 수 있는 방식입니다.
- 이번 실습 연결: 이 문서에서는 `Connect > SSH` 화면의 `SSH over exposed TCP` 명령을 기준으로 설명합니다.

## 3. 전체 흐름 먼저 보기

처음 한 번은 아래 순서로 진행하면 됩니다.

1. 내 PC에 SSH 키를 만든다.
2. 공개키를 RunPod 계정에 등록한다.
3. RunPod에서 SSH 접속을 지원하는 Pod를 생성한다.
4. Pod의 `Connect` 화면에서 SSH 명령을 복사한다.
5. PowerShell에서 먼저 접속을 시험한다.
6. 필요하면 VS Code Remote - SSH로 같은 Pod를 등록한다.

## 4. 수업 전에 준비할 것

아래 항목을 먼저 준비합니다.

1. RunPod 계정
2. Windows 11 개인 PC
3. VS Code 설치
4. VS Code 확장 `Remote - SSH` 설치
5. PowerShell 사용 가능 상태

## 5. VS Code와 SSH 준비 확인

### 5-1. VS Code 설치

VS Code가 없다면 먼저 설치합니다.

1. VS Code 공식 설치 페이지에 접속합니다.
2. Windows 버전을 설치합니다.
3. 설치가 끝나면 VS Code를 실행합니다.

### 5-2. Remote - SSH 확장 설치

1. VS Code를 엽니다.
2. 왼쪽 메뉴에서 Extensions를 선택합니다.
3. 검색창에 `Remote - SSH`를 입력합니다.
4. `ms-vscode-remote.remote-ssh` 확장을 설치합니다.

### 5-3. Windows에서 SSH 명령 확인

PowerShell을 열고 아래 명령을 실행합니다.

```powershell
ssh -V
```

버전 정보가 보이면 준비된 상태입니다.

만약 `ssh` 명령을 찾을 수 없으면 아래 순서로 `OpenSSH Client`를 설치합니다.

1. 설정
2. 시스템
3. 선택적 기능
4. 기능 추가
5. `OpenSSH Client` 설치

## 6. SSH 키 생성하기

PowerShell에서 아래 명령을 실행합니다.

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -C "your-email@example.com"
```

엔터를 누르며 기본값으로 진행해도 됩니다. 비밀번호(passphrase)는 선택 사항입니다.

생성되는 파일은 아래 두 개입니다.

- `id_ed25519`: 개인키
- `id_ed25519.pub`: 공개키

중요:

1. 개인키는 절대 다른 사람에게 보내지 않습니다.
2. 공개키만 RunPod에 등록합니다.

## 7. 공개키 확인하고 RunPod 계정에 등록하기

### 7-1. 공개키 확인

PowerShell에서 아래 명령을 실행합니다.

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

출력 예시는 아래와 같습니다.

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyGoesHere your-email@example.com
```

이 한 줄 전체를 복사합니다.

### 7-2. RunPod 계정에 공개키 등록

1. RunPod 콘솔에 로그인합니다.
2. 사용자 설정 화면으로 이동합니다.
3. `SSH Public Keys` 항목을 찾습니다.
4. 방금 복사한 공개키 한 줄 전체를 붙여 넣습니다.
5. 저장합니다.

중요:

1. `ssh-ed25519` 같은 키 종류 문자열부터 끝까지 한 줄 전체가 들어가야 합니다.
2. 중간 일부만 넣으면 안 됩니다.
3. 공개키를 등록한 뒤 **새로 시작하는 Pod**부터 자동 반영되는 것이 안전합니다.

## 8. 가장 중요한 주의점: Pod를 만든 뒤에 키를 넣었다면

RunPod 공식 문서 기준으로, **Pod가 이미 실행 중인 상태에서 나중에 공개키를 계정에 추가하면 그 키가 자동으로 주입되지 않을 수 있습니다.**

즉, 아래처럼 진행했다면 문제가 생기기 쉽습니다.

1. 먼저 Pod를 실행함
2. 나중에 RunPod 계정에 공개키를 등록함
3. 바로 SSH 접속을 시도함

이 경우 해결 방법은 둘 중 하나입니다.

1. Pod를 종료 후 다시 배포하거나 새로 생성합니다.
2. RunPod Web Terminal을 열어 `~/.ssh/authorized_keys`에 공개키를 직접 추가합니다.

초급자라면 **공개키를 먼저 등록한 뒤 Pod를 새로 생성하는 순서**를 권장합니다.

## 9. RunPod Pod 생성하기

### 9-1. 초급자에게 권장하는 선택

처음이라면 RunPod 공식 템플릿을 사용하는 편이 안전합니다.

이유:

1. 공식 템플릿은 SSH가 미리 구성된 경우가 많습니다.
2. VS Code 연결까지 검증된 사례가 많습니다.
3. 설정 실수 가능성이 줄어듭니다.

### 9-2. Pod 생성 시 확인할 것

Pod 생성 화면에서 아래 항목을 확인합니다.

1. 공식 템플릿 또는 SSH 지원 템플릿 선택
2. 공인 IP가 필요한 구성인지 확인
3. `SSH Terminal Access` 항목이 보이면 체크

RunPod 공식 안내 기준으로, VS Code나 일반 SSH 접속을 쓰려면 **SSH over exposed TCP를 지원하는 Pod**여야 합니다.

### 9-3. 커스텀 템플릿을 쓰는 경우

커스텀 템플릿은 아래 조건이 필요합니다.

1. SSH 서버가 설치되어 있어야 함
2. SSH 데몬이 실행 중이어야 함
3. TCP 22 포트가 노출되어 있어야 함
4. 공개키가 `~/.ssh/authorized_keys`에 반영되어 있어야 함

처음 실습이라면 커스텀 템플릿보다 공식 템플릿이 더 안전합니다.

## 10. Pod가 준비되었는지 확인하기

Pod가 `Running` 상태가 되면 아래 순서로 접속 정보를 확인합니다.

1. RunPod 콘솔의 Pods 페이지로 이동합니다.
2. 내가 만든 Pod를 선택합니다.
3. `Connect`를 클릭합니다.
4. `SSH` 탭을 엽니다.
5. `SSH over exposed TCP` 항목의 명령을 확인합니다.

예시는 아래처럼 보일 수 있습니다.

```bash
ssh root@213.173.108.12 -p 17445 -i ~/.ssh/id_ed25519
```

여기서 기억할 핵심 값은 아래 네 가지입니다.

- 사용자명: `root`
- 공인 IP: `213.173.108.12`
- 외부 포트: `17445`
- 개인키 경로: `~/.ssh/id_ed25519`

## 11. 먼저 PowerShell에서 SSH 접속 시험하기

VS Code로 들어가기 전에, 먼저 터미널 접속이 되는지 확인하는 것이 가장 빠릅니다.

PowerShell에서 아래와 비슷한 명령을 실행합니다.

```powershell
ssh root@213.173.108.12 -p 17445 -i "$env:USERPROFILE\.ssh\id_ed25519"
```

처음 접속이라면 아래와 비슷한 메시지가 나올 수 있습니다.

```text
The authenticity of host ... can't be established.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

내가 직접 만든 Pod가 맞다면 `yes`를 입력합니다.

정상 접속되면 원격 리눅스 셸이 열립니다.

## 12. 접속 직후 확인할 명령

연결되면 아래 명령으로 환경을 확인합니다.

```bash
whoami
pwd
ls
ls /workspace
nvidia-smi
```

확인 포인트:

1. `whoami` 결과가 `root`인지
2. `/workspace`가 보이는지
3. GPU Pod라면 `nvidia-smi`가 정상 출력되는지

## 13. VS Code에서 더 편하게 다시 접속하기

PowerShell SSH가 정상이라면, 그다음부터는 VS Code Remote - SSH를 쓰는 편이 편합니다.

### 13-1. 명령 팔레트로 SSH Host 추가

1. VS Code에서 `Ctrl+Shift+P`를 누릅니다.
2. `Remote-SSH: Add New SSH Host...`를 선택합니다.
3. RunPod `Connect` 화면에서 복사한 명령을 붙여 넣습니다.

예시:

```text
ssh root@213.173.108.12 -p 17445 -i ~/.ssh/id_ed25519
```

4. 저장할 SSH 설정 파일을 선택합니다.
5. 보통 기본 사용자 SSH 설정 파일을 선택하면 됩니다.

### 13-2. SSH config 파일을 직접 쓰는 방법

경로:

```text
%USERPROFILE%\.ssh\config
```

예시:

```ssh-config
Host my-runpod
    HostName 213.173.108.12
    User root
    Port 17445
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

이렇게 저장해 두면 다음부터는 `my-runpod`만 선택해서 접속할 수 있습니다.

### 13-3. VS Code로 실제 연결

1. `Ctrl+Shift+P`를 누릅니다.
2. `Remote-SSH: Connect to Host...`를 선택합니다.
3. 방금 추가한 Host를 선택합니다.
4. 플랫폼을 묻는 창이 뜨면 `Linux`를 선택합니다.
5. 잠시 기다리면 새 원격 창이 열립니다.

## 14. 원격 폴더 열기

연결 직후에는 작업 폴더를 직접 열어 주는 것이 좋습니다.

1. `File > Open Folder...`를 선택합니다.
2. `/workspace`를 입력하거나 선택합니다.
3. 확인을 누릅니다.

실습 파일은 가능하면 `/workspace` 아래에 저장합니다.

이유:

1. `/workspace`는 보통 영구 저장 영역으로 사용됩니다.
2. 다른 임시 경로는 Pod 변경 시 사라질 수 있습니다.

## 15. 자주 생기는 문제와 해결 방법

### 문제 1. `Permission denied (publickey)`가 나온다

의미:

1. 공개키가 Pod에 반영되지 않았거나
2. 내 PC가 다른 개인키를 사용하고 있다는 뜻입니다.

해결:

1. RunPod 계정의 `SSH Public Keys`에 올린 값이 공개키 한 줄 전체인지 확인합니다.
2. Pod를 만든 뒤에 공개키를 등록했다면 Pod를 다시 생성하거나 재배포합니다.
3. `-i` 옵션으로 개인키 경로를 정확히 지정합니다.
4. 그래도 안 되면 Web Terminal에서 `~/.ssh/authorized_keys`를 확인합니다.

### 문제 2. 비밀번호를 묻는다

RunPod 공식 안내 기준으로 키 인증이 정상이라면 보통 비밀번호를 반복해서 묻지 않아야 합니다.

해결:

1. 잘못된 비밀번호를 계속 입력하지 않습니다.
2. 공개키 등록 상태를 다시 확인합니다.
3. 개인키 경로가 맞는지 확인합니다.

### 문제 3. `SSH over exposed TCP` 항목이 보이지 않는다

의미:

1. 현재 템플릿이 이 방식을 지원하지 않을 수 있습니다.
2. 공인 IP 또는 TCP 포트 노출 조건이 맞지 않을 수 있습니다.

해결:

1. 공식 RunPod 템플릿으로 다시 만들어 봅니다.
2. Pod 생성 화면에서 `SSH Terminal Access`가 켜져 있었는지 확인합니다.
3. 커스텀 템플릿이라면 TCP 22 노출과 SSH 데몬 실행을 점검합니다.

### 문제 4. 호스트 키 경고가 다시 뜬다

Pod를 새로 만들거나 재배포하면 이전 호스트 키와 달라질 수 있습니다.

PowerShell에서 아래 명령을 실행합니다.

```powershell
ssh-keygen -R [213.173.108.12]:17445
```

그다음 다시 접속합니다.

### 문제 5. VS Code는 안 되고 PowerShell SSH만 된다

해결 순서:

1. 먼저 PowerShell SSH가 실제로 안정적으로 되는지 다시 확인합니다.
2. VS Code의 `Remote - SSH` 확장이 설치되어 있는지 확인합니다.
3. SSH config 파일의 `HostName`, `User`, `Port`, `IdentityFile` 값을 다시 확인합니다.
4. 그래도 안 되면 VS Code Host를 삭제하고 다시 등록합니다.

## 16. 초급자에게 권장하는 가장 쉬운 순서

처음에는 아래 순서만 따라 해도 됩니다.

1. 내 PC에서 SSH 키 생성
2. 공개키를 RunPod 계정의 `SSH Public Keys`에 등록
3. 공식 템플릿으로 새 Pod 생성
4. `SSH Terminal Access` 확인
5. Pod가 `Running` 상태가 되면 `Connect > SSH` 열기
6. `SSH over exposed TCP` 명령 복사
7. PowerShell에서 먼저 붙기
8. 접속이 되면 VS Code에 같은 명령 등록
9. `/workspace` 폴더 열기

## 17. 한 번에 안 되면 어디부터 볼까

아래 세 가지를 순서대로 보면 대부분 원인을 찾을 수 있습니다.

1. 공개키를 **Pod 생성 전에** RunPod 계정에 등록했는가
2. `Connect > SSH`의 `SSH over exposed TCP` 명령을 그대로 사용했는가
3. 개인키 경로가 실제 내 PC 파일과 일치하는가

이 세 가지가 맞는데도 안 되면, 템플릿의 SSH 지원 여부 또는 Pod 자체 상태를 점검해야 합니다.