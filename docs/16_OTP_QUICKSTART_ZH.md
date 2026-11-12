# OTP 部署操作手册

适用于现有 `/opt/openvpn-ui` 面板，vpn-1 部署面板和独立 OTP 服务，
vpn-2 通过安全通道使用同一认证服务。不需要 Docker，不重发原有证书。

程序不会修改 `server.conf`、移动证书、执行 rsync 或自动重启 VPN。
下面分为“安装程序”和“接入 VPN”两部分，安装不代表已经启用 VPN 动态口令。

## 一、更新面板

在 vpn-1 执行，保留原来的 `config/openvpn-ui.yaml`：

```bash
cd /opt/openvpn-ui
git pull
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
cd frontend
npm ci
npm run build
cd ..
```

继续使用现有 Python 3.9 或以上的虚拟环境，不替换系统 Python。
在原配置文件末尾新增顶层配置，注意 `otp:` 不要缩进到其他配置中：

```yaml
otp:
  enabled: true
  issuer: Company VPN
  data_dir: /var/lib/openvpn-ui/otp
  nodes: [vpn-1, vpn-2]
```

`enabled` 控制模块是否可用，不是“强制 OTP”开关。配置变化需要重启面板和
认证进程；面板内的“强制验证动态口令”开关则无须重启进程。

## 二、初始化一次

```bash
cd /opt/openvpn-ui
OPENVPN_UI_CONFIG=/opt/openvpn-ui/config/openvpn-ui.yaml .venv/bin/python -m backend.otp_store init
```

只在新增目录生成数据库、加密密钥、管理凭据和两个节点凭据。
强制验证初始为关闭；重复初始化会被拒绝，不会覆盖已有数据。
目录权限要求 700，文件权限要求 600。示例沿用你当前的 root 部署方式，
面板和 OTP 进程需使用同一个受信任系统账户。

整个 `/var/lib/openvpn-ui/otp` 目录都要安全备份，包括 `encryption.key`。
缺少密钥无法恢复绑定。备份数据库时短暂停止 OTP 服务，或使用 SQLite 的备份接口。
这些文件不要提交 Git，不要放进原来 `/etc/openvpn/` 的 rsync 同步范围。

## 三、一条命令启动 OTP

```bash
cd /opt/openvpn-ui
OPENVPN_UI_CONFIG=/opt/openvpn-ui/config/openvpn-ui.yaml .venv/bin/python -m uvicorn backend.otp_service:app --host 127.0.0.1 --port 8001 --no-access-log
```

这和原来面板进程独立，需要保持运行。另开终端检查：

```bash
curl --fail http://127.0.0.1:8001/health
```

也可以安装随项目提供的开机自启配置；这只操作新服务：

```bash
cd /opt/openvpn-ui
cp config/openvpn-ui-otp.service.example /etc/systemd/system/openvpn-ui-otp.service
systemctl daemon-reload
systemctl enable --now openvpn-ui-otp.service
systemctl status openvpn-ui-otp.service
```

不要同时用两种方式占用同一端口。8001 如果已经被占用，需要同步修改启动端口、
接入 JSON 和后续 SSH 转发配置。认证端口保持监听本机回环地址，不开放到公网。

按原方式重启面板，进入新增的 OTP 页面。管理员在 vpn-1 本地安全读取
`/var/lib/openvpn-ui/otp/admin.token`，填入“OTP 管理凭据”解锁。
凭据只保留在当前页面内存，离开 OTP 页面或点击锁定会清除。
通过 HTTPS 或 SSH 隧道访问面板，保护好管理凭据和二维码。
原有面板其他高权限接口仍需原来的访问保护，OTP 凭据不替代整个面板的登录保护。

## 四、准备 vpn-1 接入脚本

```bash
cd /opt/openvpn-ui
install -d -m 700 /var/lib/openvpn-ui/otp-client
install -m 755 scripts/otp-verify.py /var/lib/openvpn-ui/otp-client/verify.py
install -m 600 config/otp-node.example.json /var/lib/openvpn-ui/otp-client/node.json
```

默认 JSON 对应 vpn-1、本机 8001 端口和 `vpn-1.token`。路径独立于证书同步目录。
脚本只依赖 Python 标准库，vpn-2 的 Python 3.6 也可使用。

先确认两台服务器的版本和实际运行方式：

```bash
openvpn --version
systemctl cat openvpn.service
```

以下接入示例面向 OpenVPN 2.4 或以上；较老版本先核对参数支持。
如果 VPN 已配置降权账户、chroot、SELinux 或文件访问限制，要按实际进程身份
测试脚本和凭据访问权限，不要把密钥改成所有人可读。

## 五、先在独立实例验证

正式 `6999` 服务保持原样。先准备独立测试配置：不同端口、TUN 设备、未使用的
地址池，以及独立状态、日志、PID、地址池持久化文件；证书使用原有文件的绝对路径。
不要复制后直接启动而复用 `10.8.0.0/24`、管理端口或状态文件。
核对测试路由、转发和防火墙，不清空已有规则。

只在测试配置中加入：

```conf
verify-client-cert require
script-security 2
auth-user-pass-verify "/usr/bin/python3 /var/lib/openvpn-ui/otp-client/verify.py /var/lib/openvpn-ui/otp-client/node.json" via-file
auth-gen-token 3600
```

保留原来的证书验证和 `crl-verify`，不要加 `username-as-common-name` 或关闭证书验证。
脚本会要求输入的用户名与证书 CN 完全相同。验证接口异常时拒绝认证。
脚本请求超时为 5 秒，是同步认证；正式使用前需测试并发登录对 VPN 事件循环的影响。

`auth-gen-token 3600` 用于避免重新协商时重复提交已过期的 OTP。
不要加 `external-auth`，也不要通过关闭密钥重新协商规避 OTP。
有效会话令牌验证期间可能不调用 OTP 脚本，开关和重置在下次完整认证时生效。
令牌一小时到期、断线重连和切换节点的提示行为都必须用实际客户端验证。

## 六、绑定用户、配置客户端

1. 在 OTP 页选择一个已启用的原有证书用户，点击“绑定”，生成二维码。
2. 员工使用 Google Authenticator 或 Microsoft Authenticator 扫码。
3. 输入手机当前六位动态口令，点击确认绑定。二维码十分钟过期。
4. 绑定确认会消耗这枚口令，连接时等待下一枚口令。
5. 在面板开启“强制验证动态口令”，输入 `ENABLE` 确认。

复制员工现有客户端配置作为测试配置，改为测试端口，保留原来的证书文件引用，增加：

```conf
auth-user-pass
auth-retry interact
```

先核对客户端版本是否支持这些参数，按软件要求重新导入配置。
若原来已有 `auth-user-pass` 文件引用，需要调整，不能把动态口令写成固定密码。

| 登录提示 | 填写内容 |
| --- | --- |
| 私钥密码 | 原来的 `.key` 密码 |
| 用户名 | 证书 CN，与原证书用户名一致 |
| 登录密码 | 手机当前六位动态口令 |

这里不需要 CA 签发密码。现有证书继续用，不用重新创建全部用户。
重置时需要输入用户名确认，新二维码验证成功之前旧绑定继续有效。
重置不会立即踢掉在线用户；紧急断开仍使用原来的踢下线功能。
二维码就是认证密钥，须通过可信渠道交付，不上传外部二维码网站或公开分享。

## 七、vpn-2 接入同一认证服务

vpn-2 不部署第二套面板或 OTP 数据库。只安装 `verify.py`，将 `vpn-2.token`
安全传到 `/var/lib/openvpn-ui/otp-client/vpn-2.token`，权限 600。
不要把 `admin.token`、加密密钥、数据库或 vpn-1 的令牌传过去。

推荐 vpn-2 到 vpn-1 建立独立 SSH 本地转发，避免对外暴露认证端口。
使用专用转发 SSH 密钥，核验并固定主机指纹，限制该密钥只能转发到目标端口。
不要让转发依赖于它本身正在认证的 VPN 隧道。

```bash
ssh -NT -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -i /path/to/otp-tunnel-key -L 127.0.0.1:18001:127.0.0.1:8001 root@VPN1_INTERNAL_IP
```

将专用密钥路径和 vpn-1 内网地址替换成实际值。可使用项目里的
`config/openvpn-ui-otp-tunnel.service.example` 配置转发自启和失败重连。
vpn-2 的 `node.json` 为：

```json
{
  "url": "http://127.0.0.1:18001/verify",
  "node": "vpn-2",
  "token_file": "/var/lib/openvpn-ui/otp-client/vpn-2.token"
}
```

接入脚本与 JSON 路径和 vpn-1 一致，但节点名称、凭据不同。
跨主机通信由 SSH 加密；脚本拒绝内网明文 HTTP 和 HTTP 跳转。
也支持核验服务端证书的 HTTPS，详细说明见 [完整部署参考](15_OTP.md)。

## 八、验收后再正式切换

两台都要验证：正确口令成功、错误或过期口令失败、A 证书配 B 账户失败、
停用或注销证书失败、同一口令跨节点重复使用失败、长时间在线和重连正常。
关闭认证进程或 SSH 转发时，新完整认证应失败；只重启面板不应停止认证服务。
五次验证码错误后该用户锁定一分钟，两台共享记录。连续切节点需等待新口令。
手机和认证服务器须保持正确时间。

员工全部准备好后，备份两台原配置，手动加入测试通过的认证参数，分节点安排重启：

```bash
systemctl restart openvpn.service
```

这会中断该节点的现有连接；未接入的另一节点仍是绕过 OTP 的入口，直到也完成切换。
OTP 服务部署在 vpn-1，vpn-1 故障会影响两台的新完整认证，当前版本不是认证高可用集群。
丢失手机需要管理员核验身份后重置，本版未提供自助恢复码。

## 九、关闭与回滚

- 面板关闭“强制验证”：输入 `DISABLE` 确认，跳过 OTP，仍要求有效且启用的证书和
  匹配的用户名。认证进程继续运行，无须重启 VPN。
- 关闭强制验证后客户端仍有登录提示，用户名照填；密码可填非空占位值，认证后端忽略它。
- 完全移除：恢复两台备份的 `server.conf`，去掉新增认证配置，安排分别重启 VPN。
  两台都不再依赖脚本后，才停止 OTP 服务及 SSH 转发；客户端恢复原配置。
- 不要只设置 `otp.enabled: false` 或停止认证服务来“关闭 OTP”，否则已接入脚本的
  VPN 会因认证服务不可用而拒绝新的完整认证。

完整技术说明、限制与官方参考：[15_OTP.md](15_OTP.md)。
