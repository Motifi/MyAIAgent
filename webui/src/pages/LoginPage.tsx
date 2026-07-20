import React, { useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { login as apiLogin } from "../lib/api";
import type { LoginResponse, AuthView } from "../lib/types";

interface LoginPageProps {
  onLogin: (response: LoginResponse) => void;
  onNavigate: (view: AuthView) => void;
  failed?: boolean;
}

export function LoginPage({ onLogin, onNavigate, failed }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await apiLogin(username.trim(), password);
      onLogin(res);
    } catch (err: any) {
      setError(err?.message || "Login failed");
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
          <p className="text-lg font-semibold">Sign In</p>
          <p className="text-sm text-muted-foreground">
            Enter your username and password
          </p>
        </div>

        {failed && (
          <p className="text-center text-sm text-destructive">
            Please sign in to continue
          </p>
        )}
        {error && (
          <p className="text-center text-sm text-destructive">{error}</p>
        )}

        <Input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={submitting}
          autoFocus
          autoComplete="username"
        />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
          autoComplete="current-password"
        />

        <Button
          type="submit"
          className="w-full"
          disabled={!username.trim() || !password || submitting}
        >
          {submitting ? "Signing in…" : "Sign In"}
        </Button>

        <button
          type="button"
          className="text-center text-sm text-muted-foreground underline underline-offset-2 hover:text-foreground"
          onClick={() => onNavigate("register")}
        >
          Need an account? Register
        </button>
      </form>
    </div>
  );
}
