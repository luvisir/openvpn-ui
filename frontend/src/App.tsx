import { FormEvent, useEffect, useMemo, useState } from "react";

type Page = "dashboard" | "users" | "connections" | "audit" | "settings";
type PathStatus = "ok" | "missing" | "wrong_type" | "not_configured";

type PathCheck = {
  name: string;
  status: PathStatus;
  path: string;
};

type HealthResponse = {
  status: "ok" | "degraded";
  config_loaded: boolean;
  config_path: string;
  path_checks: PathCheck[];
};

type ConfigResponse = {
  config_path: string;
  app: {
    name: string;
    environment: string;
    database_url: string;
  };
  server: Record<string, unknown>;
  certificates: Record<string, unknown>;
  lifecycle: Record<string, unknown>;
  features: Record<string, boolean>;
};

type VPNUser = {
  common_name: string;
  status: "active" | "disabled" | "revoked" | "expired" | "unknown";
  certificate_path: string;
  profile_path: string;
  expires_at: string;
  revoked_at: string;
  serial: string;
  source: string;
};

type Connection = {
  node?: string;
  common_name: string;
  real_address: string;
  virtual_address: string;
  bytes_received: number;
  bytes_sent: number;
  connected_since: string;
  username: string;
  client_id: string;
  peer_id: string;
};

type ConnectionsResponse = {
  source: "replicas" | "management" | "status_file" | "none";
  nodes: Array<{
    name: string;
    role: string;
    status: "ok" | "error";
    error: string;
    connections: Connection[];
  }>;
  connections: Connection[];
};

type AuditEvent = {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  target: string;
  reason: string;
  result: string;
  error: string;
};

type AuditResponse = {
  events: AuditEvent[];
};

type OpenVPNLogResponse = {
  source: string;
  lines: string[];
};

const pages: Array<{ id: Page; label: string; title: string }> = [
  { id: "dashboard", label: "仪表盘", title: "运行概览" },
  { id: "users", label: "用户", title: "用户管理" },
  { id: "connections", label: "连接", title: "实时连接" },
  { id: "audit", label: "审计", title: "日志审计" },
  { id: "settings", label: "设置", title: "系统设置" }
];

const statusLabel: Record<PathStatus, string> = {
  ok: "正常",
  missing: "缺失",
  wrong_type: "类型不符",
  not_configured: "未配置"
};

const pathStatusClass: Record<PathStatus, string> = {
  ok: "good",
  missing: "bad",
  wrong_type: "bad",
  not_configured: "muted"
};

const userStatusLabel: Record<VPNUser["status"], string> = {
  active: "启用",
  disabled: "停用",
  revoked: "已注销",
  expired: "已过期",
  unknown: "未知"
};

export function App() {
  const [activePage, setActivePage] = useState<Page>("dashboard");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [users, setUsers] = useState<VPNUser[]>([]);
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [audit, setAudit] = useState<AuditResponse | null>(null);
  const [openvpnLog, setOpenvpnLog] = useState<OpenVPNLogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    refreshSystem();
    refreshUsers();
    refreshConnections();
  }, []);

  useEffect(() => {
    if (activePage === "audit") refreshLogs();
    if (activePage === "users") refreshUsers();
    if (activePage === "connections") refreshConnections();
  }, [activePage]);

  async function refreshSystem() {
    try {
      const [healthRes, configRes] = await Promise.all([
        fetch("/api/system/health"),
        fetch("/api/system/config")
      ]);
      if (!healthRes.ok) throw new Error(await readError(healthRes));
      if (!configRes.ok) throw new Error(await readError(configRes));
      setHealth(await healthRes.json());
      setConfig(await configRes.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接后端服务");
    }
  }

  async function refreshUsers() {
    const response = await fetch("/api/users");
    if (response.ok) {
      const payload = await response.json();
      setUsers(payload.users ?? []);
    }
  }

  async function refreshConnections() {
    try {
      const response = await fetch("/api/connections");
      if (!response.ok) throw new Error(await readError(response));
      setConnections(await response.json());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "无法读取连接状态");
    }
  }

  async function refreshLogs() {
    const [auditRes, openvpnRes] = await Promise.all([
      fetch("/api/logs/audit"),
      fetch("/api/logs/openvpn")
    ]);
    if (auditRes.ok) setAudit(await auditRes.json());
    if (openvpnRes.ok) setOpenvpnLog(await openvpnRes.json());
  }

  async function postJson(url: string, body: object) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!response.ok) throw new Error(await readError(response));
    return response.json();
  }

  async function kickUser(commonName: string, node = "") {
    try {
      const suffix = node ? `?node=${encodeURIComponent(node)}` : "";
      await postJson(`/api/connections/${encodeURIComponent(commonName)}/kick${suffix}`, {});
      setMessage(`${commonName} 已发送踢下线指令`);
      await Promise.all([refreshConnections(), refreshLogs()]);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "操作失败");
    }
  }

  const summary = useMemo(() => {
    const onlineNames = new Set(connections?.connections.map((item) => item.common_name) ?? []);
    return {
      healthyPaths: health?.path_checks.filter((item) => item.status === "ok").length ?? 0,
      missingPaths:
        health?.path_checks.filter(
          (item) => item.status !== "ok" && item.status !== "not_configured"
        ).length ?? 0,
      users: users.length,
      online: onlineNames.size,
      revoked: users.filter((item) => item.status === "revoked").length,
      disabled: users.filter((item) => item.status === "disabled").length
    };
  }, [connections, health, users]);

  const currentPage = pages.find((page) => page.id === activePage) ?? pages[0];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">OV</div>
        <nav>
          {pages.map((page) => (
            <button
              className={`nav-item ${activePage === page.id ? "active" : ""}`}
              key={page.id}
              onClick={() => setActivePage(page.id)}
              title={page.title}
            >
              {page.label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">OpenVPN Management</p>
            <h1>{currentPage.title}</h1>
          </div>
          <span className={`service-pill ${health?.status === "ok" ? "good" : "warn"}`}>
            {health?.status === "ok" ? "配置可用" : "等待配置"}
          </span>
        </header>

        {error ? (
          <section className="notice">
            <h2>配置尚未加载</h2>
            <p>{error}</p>
          </section>
        ) : (
          <>
            {activePage === "dashboard" && (
              <DashboardPage
                summary={summary}
                health={health}
                config={config}
                connections={connections}
              />
            )}
            {activePage === "users" && (
              <UsersPage
                users={users}
                config={config}
                message={message}
                onActionMessage={setMessage}
                onPost={postJson}
                onRefresh={refreshUsers}
              />
            )}
            {activePage === "connections" && (
              <ConnectionsPage
                connections={connections}
                allowKick={Boolean(config?.features.allow_kick_user)}
                message={message}
                onRefresh={refreshConnections}
                onKick={kickUser}
              />
            )}
            {activePage === "audit" && (
              <AuditPage audit={audit} openvpnLog={openvpnLog} onRefresh={refreshLogs} />
            )}
            {activePage === "settings" && (
              <SettingsPage
                health={health}
                config={config}
                message={message}
                onActionMessage={setMessage}
                onPost={postJson}
                onRefresh={refreshSystem}
              />
            )}
          </>
        )}
      </section>
    </main>
  );
}

function DashboardPage({
  summary,
  health,
  config,
  connections
}: {
  summary: {
    healthyPaths: number;
    missingPaths: number;
    users: number;
    online: number;
    revoked: number;
    disabled: number;
  };
  health: HealthResponse | null;
  config: ConfigResponse | null;
  connections: ConnectionsResponse | null;
}) {
  return (
    <>
      <section className="metrics">
        <Metric label="用户总数" value={summary.users} />
        <Metric label="当前在线" value={summary.online} />
        <Metric label="停用/注销" value={`${summary.disabled}/${summary.revoked}`} />
        <Metric label="路径正常" value={summary.healthyPaths} />
      </section>

      <section className="grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <h2>服务器路径检查</h2>
              <span>{config?.config_path ?? health?.config_path ?? "重启后生效"}</span>
            </div>
          </div>
          <PathList checks={health?.path_checks ?? []} />
        </article>
        <article className="panel">
          <div className="panel-header">
            <div>
              <h2>连接来源</h2>
              <span>{connections?.source ?? "未读取"}</span>
            </div>
          </div>
          <FeatureList features={config?.features ?? {}} />
        </article>
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function UsersPage({
  users,
  config,
  message,
  onActionMessage,
  onPost,
  onRefresh
}: {
  users: VPNUser[];
  config: ConfigResponse | null;
  message: string | null;
  onActionMessage: (value: string | null) => void;
  onPost: (url: string, body: object) => Promise<unknown>;
  onRefresh: () => Promise<void>;
}) {
  const [commonName, setCommonName] = useState("");
  const [password, setPassword] = useState("");
  const [caPassword, setCaPassword] = useState("");
  const features = config?.features ?? {};

  async function createUser(event: FormEvent) {
    event.preventDefault();
    try {
      await onPost("/api/users", { common_name: commonName, password, ca_password: caPassword });
      onActionMessage(`${commonName} 已提交创建`);
      setCommonName("");
      setPassword("");
      setCaPassword("");
      await onRefresh();
    } catch (err) {
      onActionMessage(err instanceof Error ? err.message : "创建失败");
    }
  }

  async function userAction(action: "disable" | "enable" | "revoke", user: VPNUser) {
    const actionReason = window.prompt("请输入审计原因") ?? "";
    if (action === "revoke") {
      const confirmation = window.prompt(`输入 ${user.common_name} 确认注销`) ?? "";
      if (confirmation !== user.common_name) {
        onActionMessage("注销确认不匹配，操作已取消");
        return;
      }
      const caPassword = window.prompt("请输入 CA 签发密码，用于注销证书和生成 CRL") ?? "";
      if (!caPassword) {
        onActionMessage("缺少 CA 密码，操作已取消");
        return;
      }
      await execute(`/api/users/${encodeURIComponent(user.common_name)}/revoke`, {
        reason: actionReason,
        confirmation,
        ca_password: caPassword
      });
      return;
    }
    await execute(`/api/users/${encodeURIComponent(user.common_name)}/${action}`, {
      reason: actionReason
    });
  }

  async function execute(url: string, body: object) {
    try {
      await onPost(url, body);
      onActionMessage("操作已完成");
      await onRefresh();
    } catch (err) {
      onActionMessage(err instanceof Error ? err.message : "操作失败");
    }
  }

  return (
    <section className="stack">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>新建用户</h2>
            <span>使用配置里的 create_user_command</span>
          </div>
        </div>
        <form className="form-row" onSubmit={createUser}>
          <input
            required
            value={commonName}
            onChange={(event) => setCommonName(event.target.value)}
            placeholder="common name"
          />
          <input
            required
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="客户端私钥密码"
            autoComplete="new-password"
          />
          <input
            required
            type="password"
            value={caPassword}
            onChange={(event) => setCaPassword(event.target.value)}
            placeholder="CA 签发密码"
            autoComplete="current-password"
          />
          <button className="action-button" disabled={!features.allow_create_user}>
            新建
          </button>
        </form>
        {message && <p className="inline-message">{message}</p>}
      </article>

      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>证书用户</h2>
            <span>从 Easy-RSA index.txt 和 issued 目录读取</span>
          </div>
          <button className="action-button" onClick={onRefresh}>
            刷新
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>用户</th>
                <th>状态</th>
                <th>证书</th>
                <th>Profile</th>
                <th>过期</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.common_name}>
                  <td>{user.common_name}</td>
                  <td>
                    <span className={`status ${userStatusClass(user.status)}`}>
                      {userStatusLabel[user.status]}
                    </span>
                  </td>
                  <td>{shortPath(user.certificate_path)}</td>
                  <td>{shortPath(user.profile_path)}</td>
                  <td>{user.expires_at || "-"}</td>
                  <td className="button-group">
                    <button
                      className="action-button"
                      disabled={!features.allow_disable_user || user.status !== "active"}
                      onClick={() => userAction("disable", user)}
                    >
                      停用
                    </button>
                    <button
                      className="action-button"
                      disabled={!features.allow_disable_user || user.status !== "disabled"}
                      onClick={() => userAction("enable", user)}
                    >
                      启用
                    </button>
                    <button
                      className="danger-button"
                      disabled={!features.allow_revoke_user || user.status === "revoked"}
                      onClick={() => userAction("revoke", user)}
                    >
                      注销
                    </button>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr>
                  <td colSpan={6} className="empty-cell">
                    暂无用户
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

function ConnectionsPage({
  connections,
  allowKick,
  message,
  onRefresh,
  onKick
}: {
  connections: ConnectionsResponse | null;
  allowKick: boolean;
  message: string | null;
  onRefresh: () => void;
  onKick: (commonName: string, node?: string) => void;
}) {
  return (
    <section className="stack">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>节点状态</h2>
            <span>来源：{connections?.source ?? "未读取"}</span>
          </div>
          <button className="action-button" onClick={onRefresh}>
            刷新
          </button>
        </div>
        <div className="node-grid">
          {(connections?.nodes ?? []).map((node) => (
            <div className="node-card" key={node.name}>
              <div>
                <strong>{node.name}</strong>
                <p>{node.role}</p>
              </div>
              <span className={`status ${node.status === "ok" ? "good" : "bad"}`}>
                {node.status === "ok" ? `${node.connections.length} 在线` : "异常"}
              </span>
              {node.error && <p className="node-error">{node.error}</p>}
            </div>
          ))}
          {!connections?.nodes.length && <p className="inline-message">未配置 replicas</p>}
        </div>
        {message && <p className="inline-message">{message}</p>}
      </article>

      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>在线连接</h2>
            <span>{connections?.connections.length ?? 0} 个会话</span>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>节点</th>
                <th>用户</th>
                <th>来源地址</th>
                <th>虚拟地址</th>
                <th>接收</th>
                <th>发送</th>
                <th>上线时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {(connections?.connections ?? []).map((item) => (
                <tr key={`${item.node ?? "local"}-${item.common_name}-${item.real_address}`}>
                  <td>{item.node ?? "local"}</td>
                  <td>{item.common_name}</td>
                  <td>{item.real_address}</td>
                  <td>{item.virtual_address}</td>
                  <td>{formatBytes(item.bytes_received)}</td>
                  <td>{formatBytes(item.bytes_sent)}</td>
                  <td>{item.connected_since}</td>
                  <td>
                    <button
                      className="danger-button"
                      disabled={!allowKick}
                      onClick={() => onKick(item.common_name, item.node)}
                      title={allowKick ? "踢下线" : "配置 allow_kick_user 后可用"}
                    >
                      踢下线
                    </button>
                  </td>
                </tr>
              ))}
              {!connections?.connections.length && (
                <tr>
                  <td colSpan={8} className="empty-cell">
                    暂无在线连接
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

function AuditPage({
  audit,
  openvpnLog,
  onRefresh
}: {
  audit: AuditResponse | null;
  openvpnLog: OpenVPNLogResponse | null;
  onRefresh: () => void;
}) {
  return (
    <section className="stack">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>管理审计</h2>
            <span>SQLite 本地审计事件</span>
          </div>
          <button className="action-button" onClick={onRefresh}>
            刷新
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>对象</th>
                <th>结果</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              {(audit?.events ?? []).map((event) => (
                <tr key={event.id}>
                  <td>{event.timestamp}</td>
                  <td>{event.action}</td>
                  <td>{event.target || "-"}</td>
                  <td>{event.result}</td>
                  <td>{event.reason || event.error || "-"}</td>
                </tr>
              ))}
              {!audit?.events.length && (
                <tr>
                  <td colSpan={5} className="empty-cell">
                    暂无审计事件
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>OpenVPN 日志</h2>
            <span>{openvpnLog?.source ?? "未读取"}</span>
          </div>
        </div>
        <pre className="log-view">{(openvpnLog?.lines ?? []).join("\n") || "暂无日志"}</pre>
      </article>
    </section>
  );
}

function SettingsPage({
  health,
  config,
  message,
  onActionMessage,
  onPost,
  onRefresh
}: {
  health: HealthResponse | null;
  config: ConfigResponse | null;
  message: string | null;
  onActionMessage: (value: string | null) => void;
  onPost: (url: string, body: object) => Promise<unknown>;
  onRefresh: () => Promise<void>;
}) {
  const reloadConfigured = Boolean(config?.lifecycle.reload_configured);

  async function restartOpenVPN() {
    const confirmation = window.prompt("输入 restart 确认重启 OpenVPN") ?? "";
    if (confirmation !== "restart") {
      onActionMessage("重启确认不匹配，操作已取消");
      return;
    }
    const reason = window.prompt("请输入审计原因") ?? "";
    try {
      await onPost("/api/system/openvpn/reload", { confirmation, reason });
      onActionMessage("OpenVPN 重启命令已执行");
      await onRefresh();
    } catch (err) {
      onActionMessage(err instanceof Error ? err.message : "重启失败");
    }
  }

  return (
    <section className="grid">
      <article className="panel wide">
        <div className="panel-header">
          <div>
            <h2>服务器路径检查</h2>
            <span>{config?.config_path ?? health?.config_path ?? "重启后生效"}</span>
          </div>
        </div>
        <PathList checks={health?.path_checks ?? []} />
      </article>
      <article className="panel">
        <div className="panel-header">
          <h2>功能开关</h2>
        </div>
        <FeatureList features={config?.features ?? {}} />
      </article>
      <article className="panel">
        <div className="panel-header">
          <div>
            <h2>服务操作</h2>
            <span>{reloadConfigured ? "已配置" : "未配置"}</span>
          </div>
        </div>
        <button
          className="danger-button"
          disabled={!config?.features.allow_openvpn_reload}
          onClick={restartOpenVPN}
          title={
            config?.features.allow_openvpn_reload
              ? "输入确认后执行重启命令"
              : "配置 allow_openvpn_reload 后可用"
          }
        >
          重启 OpenVPN
        </button>
        {message && <p className="inline-message">{message}</p>}
      </article>
    </section>
  );
}

function PathList({ checks }: { checks: PathCheck[] }) {
  return (
    <div className="path-list">
      {checks.map((item) => (
        <div className="path-row" key={item.name}>
          <div>
            <strong>{item.name}</strong>
            <p>{item.path || "未填写"}</p>
          </div>
          <span className={`status ${pathStatusClass[item.status]}`}>
            {statusLabel[item.status]}
          </span>
        </div>
      ))}
    </div>
  );
}

function FeatureList({ features }: { features: Record<string, boolean> }) {
  return (
    <div className="feature-list">
      {Object.entries(features).map(([name, enabled]) => (
        <div className="feature-row" key={name}>
          <span>{name}</span>
          <strong>{enabled ? "开启" : "关闭"}</strong>
        </div>
      ))}
    </div>
  );
}

function userStatusClass(status: VPNUser["status"]) {
  if (status === "active") return "good";
  if (status === "revoked" || status === "expired") return "bad";
  if (status === "disabled") return "warn";
  return "muted";
}

function shortPath(path: string) {
  if (!path) return "-";
  const parts = path.split("/");
  return parts.slice(-3).join("/");
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

async function readError(response: Response) {
  try {
    const payload = await response.json();
    return formatErrorDetail(payload.detail) || response.statusText;
  } catch {
    return response.statusText;
  }
}

function formatErrorDetail(detail: unknown): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const location = "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : "";
          const message = typeof item.msg === "string" ? item.msg : JSON.stringify(item.msg);
          return location ? `${location}: ${message}` : message;
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (typeof detail === "object") return JSON.stringify(detail);
  return String(detail);
}
