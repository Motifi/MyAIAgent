import React, { useEffect, useState } from "react";
import { Button } from "../ui/button";
import {
  fetchUsers,
  fetchPendingUsers,
  approveUser,
  rejectUser,
  changeUserRole,
} from "../../lib/api";
import type { UserInfo } from "../../lib/types";

interface UsersManagementProps {
  token: string;
  currentUser: UserInfo;
}

export function UsersManagement({ token, currentUser }: UsersManagementProps) {
  const [tab, setTab] = useState<"active" | "pending">("active");
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const res =
        tab === "pending"
          ? await fetchPendingUsers(token)
          : await fetchUsers(token);
      setUsers(res.users || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [tab, token]);

  const handleApprove = async (userId: string) => {
    try {
      await approveUser(token, userId);
      loadUsers();
    } catch (err: any) {
      setError(err?.message || "Failed to approve");
    }
  };

  const handleReject = async (userId: string) => {
    try {
      await rejectUser(token, userId);
      loadUsers();
    } catch (err: any) {
      setError(err?.message || "Failed to reject");
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await changeUserRole(token, userId, newRole);
      loadUsers();
    } catch (err: any) {
      setError(err?.message || "Failed to change role");
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-2">
        <button
          className={`px-3 py-1 text-sm rounded ${
            tab === "active"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("active")}
        >
          Active Users
        </button>
        <button
          className={`px-3 py-1 text-sm rounded ${
            tab === "pending"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("pending")}
        >
          Pending Approvals
        </button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : users.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {tab === "pending" ? "No pending users" : "No users found"}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {users.map((u) => (
            <div
              key={u.id}
              className="flex items-center justify-between rounded border p-3"
            >
              <div>
                <p className="text-sm font-medium">
                  {u.display_name || u.username}
                  {u.username !== u.display_name && (
                    <span className="ml-1 text-xs text-muted-foreground">
                      @{u.username}
                    </span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  Role: {u.role} · Status: {u.status}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {tab === "pending" && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleApprove(u.id)}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive"
                      onClick={() => handleReject(u.id)}
                    >
                      Reject
                    </Button>
                  </>
                )}
                {tab === "active" &&
                  currentUser.role === "super_admin" &&
                  u.role !== "super_admin" && (
                    <select
                      className="text-xs border rounded px-2 py-1"
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
