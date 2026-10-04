import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

export type AppPath =
  | "/"
  | "/work-queue"
  | "/households"
  | `/households/${string}`;

function currentPath(): AppPath {
  const path = window.location.pathname;
  if (path === "/work-queue") return "/work-queue";
  if (path === "/households") return "/households";
  if (path.startsWith("/households/") && path.length > "/households/".length) {
    return path as AppPath;
  }
  return "/";
}

export function useAppPath(): AppPath {
  const [path, setPath] = useState<AppPath>(() => currentPath());

  useEffect(() => {
    const onPopState = () => setPath(currentPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  return path;
}

export function navigate(path: AppPath): void {
  if (window.location.pathname === path) {
    return;
  }
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function AppLink({
  to,
  children,
  className = "",
}: {
  to: AppPath;
  children: ReactNode;
  className?: string;
}) {
  function onClick(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    event.preventDefault();
    navigate(to);
  }

  return (
    <a className={className} href={to} onClick={onClick}>
      {children}
    </a>
  );
}
