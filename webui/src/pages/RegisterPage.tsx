import React, { useState, useMemo } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { register as apiRegister } from "../lib/api";
import type { RegisterResponse, AuthView } from "../lib/types";

const USERNAME_RE = /^[a-zA-Z][a-zA-Z0-9_]{1,31}$/;

interface RegisterPageProps {
  onRegistered: (response: RegisterResponse) => void;
  onNavigate: (view: AuthView) => void;
}

export function RegisterPage({ onRegistered, onNavigate }: RegisterPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const usernameHint = useMemo(() => {
    if (!username) return null;
    if (!USERNAME_RE.test(username)) {
      return "只能包含英文字母、数字和下划线，以字母开头（2-32位）";
    }
    return null;
  }, [username]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const res = await apiRegister(
        username.trim(),
        password,
        (displayName || username).trim(),
      );
      onRegistered(res);
    } catch (err: any) {
      setError(err?.message || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full w-full items-center justify-center px-6">
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-sm flex-col gap-4"
      >
        <div className="flex flex-col items-center gap-1 text-center">
          <p className="text-lg font-semibold">Create Account</p>
          <p className="text-sm text-muted-foreground">
            Register — an admin will approve your account
          </p>
        </div>

        {error && (
          <p className="text-center text-sm text-destructive">{error}</p>
        )}

        <Input
          type="text"
          placeholder="用户名（英文+数字+下划线）"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={submitting}
          autoFocus
          autoComplete="username"
        />
        {usernameHint && (
          <p className="text-xs text-amber-600 dark:text-amber-400">{usernameHint}</p>
        )}
        <Input
          type="text"
          placeholder="Display name (optional)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          disabled={submitting}
        />
        <Input
          type="password"
          placeholder="Password (min. 6 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
          autoComplete="new-password"
        />

        <Button
          type="submit"
          className="w-full"
          disabled={!USERNAME_RE.test(username) || password.length < 6 || submitting}
        >
          {submitting ? "Creating account…" : "Create Account"}
        </Button>

        <button
          type="button"
          className="text-center text-sm text-muted-foreground underline underline-offset-2 hover:text-foreground"
          onClick={() => onNavigate("login")}
        >
          Already have an account? Sign in
        </button>
      </form>
    </div>
  );
}
