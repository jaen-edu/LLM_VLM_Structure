# 학생용 가이드: Windows 11에서 VS Code로 RunPod Pod 접속하기

## 1. 이 가이드의 목적

이 문서는 학교 네트워크에서 22번 포트가 막혀 있는 상황에서도, Windows 11의 VS Code를 이용해 강사가 준비한 RunPod Pod에 접속하는 방법을 단계별로 설명합니다.

> **왜 접속이 가능한가요?**
> RunPod는 Pod 내부의 SSH 22번을 외부의 다른 포트로 연결해 줄 수 있습니다. 그래서 학교에서 22번이 막혀 있어도, 강사가 알려준 외부 포트로 접속하면 VS Code Remote-SSH를 사용할 수 있습니다.

## 2. 수업 전에 준비할 것

아래 네 가지를 먼저 준비합니다.

1. Windows 11 PC
2. VS Code 설치
3. VS Code 확장 `Remote - SSH` 설치
4. SSH 키 생성 후 공개키를 강사에게 제출

## 3. VS Code 설치

VS Code가 없다면 먼저 설치합니다.

1. VS Code 설치 페이지에 접속합니다.
2. Windows 버전을 설치합니다.
3. 설치가 끝나면 실행합니다.

## 4. Remote - SSH 확장 설치

1. VS Code를 실행합니다.
2. 왼쪽 메뉴에서 Extensions를 엽니다.
3. 검색창에 `Remote - SSH`를 입력합니다.
4. `ms-vscode-remote.remote-ssh` 확장을 설치합니다.

## 5. Windows 11에서 SSH 사용 가능 여부 확인

Windows 11에는 보통 OpenSSH Client가 포함되어 있습니다. 아래 명령으로 확인합니다.

PowerShell을 열고 실행합니다.

```powershell
ssh -V
```

버전 정보가 보이면 준비된 상태입니다.

만약 `ssh` 명령을 찾을 수 없으면, Windows 설정에서 `OpenSSH Client`를 추가 설치해야 합니다.

설치 경로 예시:

1. 설정
2. 시스템
3. 선택적 기능
4. 기능 추가
5. `OpenSSH Client` 설치

## 6. SSH 키 생성하기

강사가 공개키를 미리 받아 Pod에 등록해야 하므로, 수업 전에 SSH 키를 생성해야 합니다.

PowerShell에서 아래 명령을 실행합니다.

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -C "your-name"
```

설명:

- `id_ed25519`: 개인키 파일
- `id_ed25519.pub`: 공개키 파일

엔터를 누르며 기본값으로 진행해도 됩니다. 비밀번호(passphrase)는 선택 사항입니다.

## 7. 공개키를 강사에게 제출하기

아래 명령으로 공개키 내용을 확인합니다.

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

출력 예시:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyGoesHere your-name
```

이 한 줄 전체를 강사에게 제출합니다.

중요:

1. `.pub` 파일 내용만 제출합니다.
2. 개인키 `id_ed25519` 파일은 절대 다른 사람에게 보내지 않습니다.

## 8. 수업 시간에 강사에게 받아야 하는 정보

강사는 학생마다 다른 Pod를 배정합니다. 아래 정보를 받아야 합니다.

- Pod 별칭 또는 번호
- 공인 IP 주소
- 외부 SSH 포트
- 사용자명 `root`
- 원격 작업 폴더 `/workspace`

예시:

- Pod 이름: `rp-class-07`
- IP: `213.173.108.12`
- Port: `17445`
- User: `root`
- Folder: `/workspace`

## 9. 먼저 네트워크 연결 확인하기

학교 방화벽이 22번만 막는 경우에는 접속이 가능하지만, 만약 임의의 외부 고포트까지 막혀 있으면 접속이 안 됩니다.

아래 명령으로 먼저 확인합니다.

```powershell
Test-NetConnection 213.173.108.12 -Port 17445
```

결과에서 `TcpTestSucceeded : True`가 보이면 다음 단계로 진행합니다.

`False`가 나오면 바로 강사에게 알립니다.

## 10. VS Code에 SSH Host 등록하기

가장 쉬운 방법은 VS Code 명령 팔레트에서 SSH Host를 추가하는 것입니다.

1. VS Code에서 `Ctrl+Shift+P`를 누릅니다.
2. `Remote-SSH: Add New SSH Host...`를 선택합니다.
3. 아래 형식으로 입력합니다.

```text
ssh root@213.173.108.12 -p 17445
```

4. 저장할 SSH 설정 파일을 선택합니다.
5. 보통 기본값인 사용자 SSH 설정 파일을 선택하면 됩니다.

## 11. 직접 SSH 설정 파일을 편집하는 방법

필요하면 아래 경로의 SSH 설정 파일을 직접 수정할 수도 있습니다.

경로:

```text
%USERPROFILE%\.ssh\config
```

예시:

```ssh-config
Host rp-class-07
    HostName 213.173.108.12
    User root
    Port 17445
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
```

이 방식의 장점은 나중에 다시 접속할 때 `rp-class-07`만 선택하면 된다는 점입니다.

## 12. Pod에 접속하기

1. `Ctrl+Shift+P`를 누릅니다.
2. `Remote-SSH: Connect to Host...`를 선택합니다.
3. 방금 추가한 Host를 선택합니다.
4. 처음 접속하면 호스트 지문 확인 메시지가 나올 수 있습니다.
5. 본인이 받은 Pod가 맞다면 `Continue` 또는 `yes`를 선택합니다.
6. 플랫폼을 묻는 창이 뜨면 `Linux`를 선택합니다.

정상적으로 연결되면 새 VS Code 창이 열립니다.

## 13. 원격 폴더 열기

연결 직후에는 빈 창처럼 보일 수 있습니다. 아래 순서로 원격 폴더를 엽니다.

1. `File > Open Folder...`를 선택합니다.
2. `/workspace`를 입력하거나 선택합니다.
3. 확인을 누릅니다.

실습 파일은 가능하면 `/workspace` 아래에 저장합니다.

이유:

- `/workspace`는 보통 영구 저장 영역으로 사용됩니다.
- `/tmp` 같은 위치는 Pod가 중지되면 사라질 수 있습니다.

## 14. 연결 후 바로 해볼 것

VS Code 하단 왼쪽에 원격 연결 표시가 보이면 정상입니다.

터미널을 열고 아래 명령을 실행해 봅니다.

```bash
pwd
ls
nvidia-smi
```

`nvidia-smi`가 정상적으로 나오면 GPU Pod에 잘 연결된 것입니다.

## 15. 실습 중 꼭 지킬 것

1. 강사가 지시하지 않았는데 Pod를 중지하거나 재시작하지 않습니다.
2. 파일은 `/workspace`에 저장합니다.
3. 접속 정보는 다른 학생과 섞지 않습니다.
4. 연결이 끊기면 먼저 강사에게 포트가 바뀌었는지 확인합니다.

## 16. 웹 서비스나 노트북 포트 사용하기

실습 중 웹 앱이나 노트북 서버를 띄우면, VS Code가 포트 포워딩을 제안할 수 있습니다.

예를 들어 원격 Pod에서 아래처럼 실행했다면:

```bash
python -m http.server 8000
```

VS Code가 8000 포트를 자동으로 인식하고 로컬로 전달할 수 있습니다.

필요하면 아래 명령으로 직접 포트를 열 수도 있습니다.

1. `Ctrl+Shift+P`
2. `Ports: Forward a Port`
3. 원격 포트 번호 입력

## 17. 자주 발생하는 문제와 해결 방법

### 문제 1. `Permission denied (publickey)`가 나온다

의미:

- 내 공개키가 Pod에 등록되지 않았거나
- 내 PC가 올바른 개인키를 쓰지 못하고 있다는 뜻입니다.

해결:

1. 내가 공개키를 강사에게 제대로 제출했는지 확인합니다.
2. 공개키는 `.pub` 파일 내용 전체여야 합니다.
3. 강사에게 내 Pod에 공개키가 들어갔는지 확인 요청합니다.

### 문제 2. 연결이 오래 걸리거나 멈춘다

해결 순서:

1. `Test-NetConnection`으로 IP와 포트가 열려 있는지 다시 확인합니다.
2. Pod가 아직 완전히 올라오지 않았을 수 있으니 잠시 뒤 다시 시도합니다.
3. 그래도 안 되면 강사에게 예비 Pod 배정을 요청합니다.

### 문제 3. 호스트 키 경고가 뜬다

Pod가 재배포되면 이전 기록과 달라질 수 있습니다.

PowerShell에서 아래 명령을 실행합니다.

```powershell
ssh-keygen -R [213.173.108.12]:17445
```

그 뒤 다시 접속합니다.

### 문제 4. 비밀번호를 물어본다

기본 운영 방식이 공개키라면, 보통은 비밀번호를 묻지 않아야 정상입니다.

해결:

1. 먼저 함부로 아무 비밀번호나 반복 입력하지 않습니다.
2. 강사에게 공개키 등록 상태를 확인해 달라고 요청합니다.
3. 강사가 비밀번호 기반 접속으로 운영한다고 별도 안내한 경우에만 전달받은 비밀번호를 입력합니다.

### 문제 5. VS Code Server 설치 오류가 난다

드물게 원격 서버 설치가 꼬일 수 있습니다.

이 경우 강사 안내에 따라 아래 폴더를 삭제하고 다시 접속할 수 있습니다.

```bash
rm -rf ~/.vscode-server
```

## 18. 빠른 접속 요약

가장 짧게 정리하면 아래 순서입니다.

1. VS Code 설치
2. `Remote - SSH` 설치
3. PowerShell에서 SSH 키 생성
4. 공개키를 강사에게 제출
5. 강사에게 받은 IP/포트로 SSH Host 추가
6. `Remote-SSH: Connect to Host` 실행
7. `/workspace` 열기

## 19. 접속이 끝까지 안 되면 확인할 것

아래 세 가지를 순서대로 확인하면 대부분 해결됩니다.

1. 내 공개키를 강사에게 제출했는가
2. 강사가 준 IP와 포트를 정확히 입력했는가
3. `Test-NetConnection` 결과가 `True`인가

세 가지가 모두 맞는데도 접속이 안 되면, 네트워크 또는 Pod 자체 문제일 가능성이 높으므로 강사에게 바로 알려 예비 Pod로 전환하는 것이 가장 빠릅니다.
