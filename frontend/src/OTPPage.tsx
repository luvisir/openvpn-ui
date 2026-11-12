import { FormEvent, useEffect, useState } from "react";

type User = { common_name: string; status: string };
type OTPStatus = {
  enforced: boolean;
  users: Record<string, { bound: boolean; pending: boolean }>;
  events: { id: number; at: number; action: string; target: string; node: string; result: string; detail: string }[];
};
type Enrollment = { name: string; qr: string; expires_in: number };

const detailLabels: Record<string, string> = {
  "enabled": "已开启强制验证",
  "disabled": "已关闭强制验证",
  "OTP bypassed by administrator policy": "按管理员策略跳过动态口令",
  "inactive or unknown certificate user": "证书用户不存在或未启用",
  "certificate and username mismatch": "用户名与证书不匹配",
  "OTP not enrolled": "尚未绑定动态口令",
  "rate limited": "尝试次数过多，请稍后重试",
  "invalid, expired or reused OTP": "口令错误、已过期或已使用",
  "Enrollment expired; generate a new QR code": "绑定已过期，请重新生成二维码",
  "Invalid verification code": "动态口令不正确",
  "Too many attempts; wait one minute": "尝试次数过多，请等待一分钟",
  "OTP administrator credential required": "OTP 管理凭据不正确",
  "OTP is disabled or not initialized": "OTP 模块未启用或尚未初始化"
};

export function OTPPage({ enabled, users }: { enabled: boolean; users: User[] }) {
  const [credential, setCredential] = useState("");
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<OTPStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [code, setCode] = useState("");
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [policy, setPolicy] = useState<boolean | null>(null);

  useEffect(() => {
    if (!enrollment) return;
    const timer = window.setTimeout(() => {
      setEnrollment(null);
      setCode("");
      setError("二维码已过期，请重新生成");
    }, enrollment.expires_in * 1000);
    return () => window.clearTimeout(timer);
  }, [enrollment]);

  async function request(path: string, body?: object, auth = token) {
    const response = await fetch(`/api/otp${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: `Bearer ${auth}`, "Content-Type": "application/json" },
      cache: "no-store",
      ...(body === undefined ? {} : { body: JSON.stringify(body) })
    });
    if (!response.ok) {
      if (response.status === 401) { setToken(""); setStatus(null); setEnrollment(null); }
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? (detailLabels[data.detail] ?? data.detail) : "操作失败，请检查输入及服务状态");
    }
    return response.json();
  }

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); }
    catch (err) { setError(err instanceof Error ? err.message : "操作失败"); }
    finally { setBusy(false); }
  }

  function unlock(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const data = await request("", undefined, credential);
      setStatus(data); setToken(credential); setCredential("");
    });
  }

  function startEnrollment(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      setEnrollment(await request(`/users/${encodeURIComponent(selected)}/enroll`, { confirmation }));
      setCode(""); setConfirmation("");
      setStatus(await request(""));
    });
  }

  function confirmEnrollment(event: FormEvent) {
    event.preventDefault();
    if (!enrollment) return;
    void run(async () => {
      await request(`/users/${encodeURIComponent(enrollment.name)}/confirm`, { code });
      setEnrollment(null); setCode(""); setSelected("");
      setStatus(await request(""));
      setMessage("绑定已确认。下次连接请使用手机下一枚动态口令。");
    });
  }

  function changePolicy(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      setStatus(await request("/policy", { enforced: policy, confirmation }));
      setPolicy(null); setConfirmation("");
      setMessage("认证策略已保存。已有会话不会立即断开，完整认证时使用新策略。");
    });
  }

  if (!enabled) return <section className="notice"><h2>OTP 未启用</h2></section>;

  return <section className="stack">
    <article className="panel">
      <div className="panel-header">
        <h2>认证策略</h2>
        {token && <div className="button-group">
          <button className="action-button" disabled={busy} onClick={() => void run(async () => { setStatus(await request("")); })} aria-label="刷新 OTP 状态" title="刷新 OTP 状态">↻</button>
          <button className="action-button" disabled={busy} onClick={() => { setToken(""); setStatus(null); setEnrollment(null); setSelected(""); setPolicy(null); setConfirmation(""); setCode(""); }} aria-label="锁定 OTP 管理" title="锁定 OTP 管理">锁定</button>
        </div>}
      </div>
      {!token ? <form className="otp-form" onSubmit={unlock}>
        <label>OTP 管理凭据<input type="password" autoComplete="off" required value={credential} onChange={e => setCredential(e.target.value)} /></label>
        <button className="action-button" disabled={busy}>解锁</button>
      </form> : <label className="otp-toggle">
        <input type="checkbox" checked={Boolean(status?.enforced)} disabled={busy || policy !== null}
          onChange={e => { setPolicy(e.target.checked); setConfirmation(""); }} />
        强制验证动态口令
        <span className={`status ${status?.enforced ? "good" : "warn"}`}>{status?.enforced ? "强制验证" : "未强制验证"}</span>
      </label>}
      {policy !== null && token && <form className="otp-confirm" onSubmit={changePolicy}>
        <p>{policy ? "开启后，未绑定动态口令的用户无法通过完整认证。" : "关闭后，完整认证将跳过动态口令校验，仍需运行认证服务。"}</p>
        <label>输入 {policy ? "ENABLE" : "DISABLE"} 确认<input required value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>
        <div className="button-group"><button className="danger-button" disabled={busy || confirmation !== (policy ? "ENABLE" : "DISABLE")}>确认变更</button>
          <button type="button" className="action-button" disabled={busy} onClick={() => { setPolicy(null); setConfirmation(""); }}>取消</button></div>
      </form>}
      {error && <p className="inline-message" role="alert">{error}</p>}
      {message && <p className="inline-message" role="status">{message}</p>}
    </article>

    {token && status && <>
      <article className="panel">
        <div className="panel-header"><h2>用户绑定</h2></div>
        {selected && !enrollment && <form className="otp-confirm" onSubmit={startEnrollment}>
          <strong>{selected}</strong>
          {status.users[selected]?.bound && <label>输入用户名确认重置<input required value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>}
          <div className="button-group"><button className="action-button" disabled={busy || Boolean(status.users[selected]?.bound && confirmation !== selected)}>生成绑定二维码</button>
            <button type="button" className="action-button" disabled={busy} onClick={() => { setSelected(""); setConfirmation(""); }}>取消</button></div>
        </form>}
        {enrollment && <form className="otp-enrollment" onSubmit={confirmEnrollment}>
          <div><h3>{enrollment.name}</h3><img src={enrollment.qr} width="256" height="256" alt={`${enrollment.name} 的 OTP 绑定二维码`} /></div>
          <div className="otp-confirm"><label>手机动态口令<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={e => setCode(e.target.value)} /></label>
            <div className="button-group"><button className="action-button" disabled={busy}>确认绑定</button>
              <button type="button" className="action-button" disabled={busy} onClick={() => void run(async () => {
                await request(`/users/${encodeURIComponent(enrollment.name)}/cancel`, {});
                setEnrollment(null); setCode(""); setSelected(""); setStatus(await request(""));
              })}>取消绑定</button></div>
          </div>
        </form>}
        <div className="table-wrap"><table className="otp-users-table"><thead><tr><th>用户</th><th>证书状态</th><th>动态口令</th><th>操作</th></tr></thead>
          <tbody>{users.map(user => <tr key={user.common_name}><td>{user.common_name}</td><td>{({ active: "启用", disabled: "停用", revoked: "已注销", expired: "已过期" } as Record<string, string>)[user.status] ?? "未知"}</td>
            <td><span className={`status ${status.users[user.common_name]?.bound ? "good" : "muted"}`}>{status.users[user.common_name]?.bound ? "已绑定" : "未绑定"}</span>{status.users[user.common_name]?.pending && " · 待确认"}</td>
            <td><button className="action-button" disabled={busy || Boolean(enrollment) || policy !== null || user.status !== "active"} onClick={() => { setSelected(user.common_name); setConfirmation(""); }}>{status.users[user.common_name]?.bound ? "重置" : "绑定"}</button></td></tr>)}
            {!users.length && <tr><td colSpan={4} className="empty-cell">暂无用户</td></tr>}
          </tbody></table></div>
      </article>
      <article className="panel">
        <div className="panel-header"><h2>认证审计</h2></div>
        <div className="table-wrap"><table><thead><tr><th>时间</th><th>操作</th><th>用户</th><th>节点</th><th>结果</th><th>详情</th></tr></thead>
          <tbody>{status.events.map(e => <tr key={e.id}><td>{new Date(e.at * 1000).toLocaleString()}</td><td>{({ "otp.authentication": "连接认证", "otp.enforcement": "策略变更", "otp.enrollment.started": "发起绑定", "otp.enrollment.confirmed": "确认绑定", "otp.enrollment.cancelled": "取消绑定" } as Record<string, string>)[e.action] ?? e.action}</td><td>{e.target || "-"}</td><td>{e.node || "-"}</td><td>{e.result === "success" ? "成功" : "失败"}</td><td>{detailLabels[e.detail] ?? (e.detail || "-")}</td></tr>)}
            {!status.events.length && <tr><td colSpan={6} className="empty-cell">暂无认证记录</td></tr>}
          </tbody></table></div>
      </article>
    </>}
  </section>;
}
