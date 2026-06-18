"use client";

import { useEffect, useState } from "react";

import { BACKEND_URL } from "@/lib/api";

type Status = "checking" | "online" | "offline";

export function AgentStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let active = true;
    fetch(`${BACKEND_URL}/health`)
      .then((res) => {
        if (active) setStatus(res.ok ? "online" : "offline");
      })
      .catch(() => {
        if (active) setStatus("offline");
      });
    return () => {
      active = false;
    };
  }, []);

  const label =
    status === "checking"
      ? "Checking agent service…"
      : status === "online"
        ? "Agent service online"
        : "Agent service unreachable";

  return (
    <span className="badge">
      <span
        className={
          status === "online"
            ? "dot dot-ok"
            : status === "offline"
              ? "dot dot-err"
              : "dot"
        }
      />
      {label}
    </span>
  );
}
