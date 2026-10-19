import { Compass } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button, Card } from "../components/ui";

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-dvh items-center justify-center bg-surface-0 px-4">
      <Card className="w-full max-w-md p-8 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          <Compass className="size-5" aria-hidden />
        </div>
        <p className="tnum mt-5 text-4xl font-bold tracking-tight">404</p>
        <h1 className="mt-2 text-lg font-semibold">This page does not exist</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The link may be out of date, or the page may have moved.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="secondary" onClick={() => navigate(-1)}>
            Go back
          </Button>
          <Button onClick={() => navigate("/app")}>Open dashboard</Button>
        </div>
      </Card>
    </div>
  );
}
