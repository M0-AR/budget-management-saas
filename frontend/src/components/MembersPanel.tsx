/**
 * Workspace members & invitations.
 *
 * No email delivery: an invitation is a single-use signed link the admin
 * copies and shares directly (Slack-style "copy invite link"). Reading the
 * member list is open to every role; everything else requires admin.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Copy, Link2, MailPlus, Trash2, X } from "lucide-react";

import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  Field,
  Input,
  LoadingPanel,
  Select,
  useToast,
} from "./ui";
import { api, ApiRequestError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { AssignableRole, Invite, InviteCreated, Member, Role } from "../lib/types";
import { cn } from "../lib/utils";

const ROLE_LABEL: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

const ROLE_BADGE: Record<Role, "neutral" | "accent" | "success" | "warning"> = {
  owner: "success",
  admin: "accent",
  member: "neutral",
  viewer: "warning",
};

function initialsOf(member: Member): string {
  const source = member.full_name.trim() || member.email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0]! + parts[1][0]!).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

function formatDay(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function errorDetail(caught: unknown, fallback: string): string {
  return caught instanceof ApiRequestError ? caught.detail : fallback;
}

export function MembersPanel() {
  const { user } = useAuth();
  const { push } = useToast();
  const queryClient = useQueryClient();

  const myRole = user?.role ?? "viewer";
  const canManage = myRole === "owner" || myRole === "admin";

  const [removing, setRemoving] = useState<Member | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<AssignableRole>("member");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [issued, setIssued] = useState<InviteCreated | null>(null);

  const membersQuery = useQuery({
    queryKey: ["members"],
    queryFn: () => api.get<Member[]>("/api/v1/members"),
  });

  const invitesQuery = useQuery({
    queryKey: ["invites"],
    queryFn: () => api.get<Invite[]>("/api/v1/members/invites"),
    enabled: canManage,
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: AssignableRole }) =>
      api.patch<Member>(`/api/v1/members/${id}`, { role }),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["members"] });
      push({ tone: "success", title: `${updated.full_name || updated.email} is now ${ROLE_LABEL[updated.role].toLowerCase()}` });
    },
    onError: (caught) =>
      push({ tone: "danger", title: errorDetail(caught, "Unable to change that role") }),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/members/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members"] });
      push({ tone: "success", title: "Member removed" });
      setRemoving(null);
    },
    onError: (caught) => {
      push({ tone: "danger", title: errorDetail(caught, "Unable to remove that member") });
      setRemoving(null);
    },
  });

  const inviteMutation = useMutation({
    mutationFn: (payload: { email: string; role: AssignableRole }) =>
      api.post<InviteCreated>("/api/v1/members/invites", payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["invites"] });
      setIssued(created);
      setInviteEmail("");
      setInviteError(null);
      push({ tone: "success", title: `Invitation ready for ${created.email}` });
    },
    onError: (caught) =>
      setInviteError(errorDetail(caught, "Unable to create that invitation")),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/members/invites/${id}`),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["invites"] });
      setIssued((current) => (current && current.id === id ? null : current));
      push({ tone: "success", title: "Invitation revoked" });
    },
    onError: (caught) =>
      push({ tone: "danger", title: errorDetail(caught, "Unable to revoke that invitation") }),
  });

  const members = membersQuery.data ?? [];
  const invites = invitesQuery.data ?? [];

  const grantableRoles = useMemo<AssignableRole[]>(
    () => (myRole === "owner" ? ["admin", "member", "viewer"] : ["member", "viewer"]),
    [myRole],
  );

  const canManageTarget = (target: Member): boolean => {
    if (!canManage || target.id === user?.id || target.role === "owner") return false;
    if (myRole === "owner") return true;
    return target.role === "member" || target.role === "viewer";
  };

  const inviteLink = issued
    ? `${window.location.origin}/register?invite=${encodeURIComponent(issued.token)}`
    : null;

  const copyInviteLink = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      push({ tone: "success", title: "Invite link copied" });
    } catch {
      push({
        tone: "danger",
        title: "Copy failed",
        description: "Select the link and copy it manually.",
      });
    }
  };

  const submitInvite = () => {
    setInviteError(null);
    const email = inviteEmail.trim();
    if (!email) {
      setInviteError("Enter the email address to invite.");
      return;
    }
    inviteMutation.mutate({ email, role: inviteRole });
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader
          title="Members"
          subtitle="Everyone with access to this workspace."
          action={
            !canManage ? <Badge tone="warning">Read-only for your role</Badge> : null
          }
        />
        {membersQuery.isLoading ? (
          <LoadingPanel />
        ) : membersQuery.isError ? (
          <p role="alert" className="px-5 py-4 text-sm font-medium text-danger">
            {errorDetail(membersQuery.error, "Unable to load members")}
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {members.map((member) => (
              <li key={member.id} className="flex items-center gap-3 px-5 py-3.5">
                <span
                  aria-hidden
                  className="flex size-9 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold text-ink-muted"
                >
                  {initialsOf(member)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {member.full_name || member.email}
                    {member.id === user?.id ? (
                      <span className="ml-1.5 text-xs font-normal text-ink-muted">(you)</span>
                    ) : null}
                  </p>
                  <p className="truncate text-xs text-ink-muted">
                    {member.email} · joined {formatDay(member.created_at)}
                  </p>
                </div>
                {canManageTarget(member) ? (
                  <Select
                    aria-label={`Role for ${member.full_name || member.email}`}
                    className="h-8 w-28 text-xs"
                    value={member.role}
                    onChange={(event) =>
                      roleMutation.mutate({ id: member.id, role: event.target.value as AssignableRole })
                    }
                  >
                    {grantableRoles.map((role) => (
                      <option key={role} value={role}>
                        {ROLE_LABEL[role]}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Badge tone={ROLE_BADGE[member.role]} dot>
                    {ROLE_LABEL[member.role]}
                  </Badge>
                )}
                {canManageTarget(member) ? (
                  <button
                    type="button"
                    aria-label={`Remove ${member.full_name || member.email}`}
                    onClick={() => setRemoving(member)}
                    className="rounded-lg p-2 text-ink-muted transition hover:bg-danger-soft hover:text-danger"
                  >
                    <Trash2 className="size-4" />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="space-y-5">
        {canManage ? (
          <Card>
            <CardHeader
              title="Invite by link"
              subtitle="Create a single-use link — share it with the person you're inviting."
            />
            <div className="space-y-3.5 p-5">
              {issued && inviteLink ? (
                <div className="space-y-3 rounded-xl border border-accent/30 bg-accent-soft px-3.5 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">
                      Link ready for <span className="font-semibold">{issued.email}</span>
                    </p>
                    <button
                      type="button"
                      aria-label="Dismiss invite link"
                      onClick={() => setIssued(null)}
                      className="rounded-md p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                  <p className="break-all rounded-lg border border-line bg-surface-1 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-ink-muted">
                    {inviteLink}
                  </p>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-ink-muted">
                      Expires {formatDay(issued.expires_at)} · works once
                    </p>
                    <Button icon={<Copy className="size-4" />} onClick={copyInviteLink}>
                      Copy link
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <Field label="Email address">
                    {(id) => (
                      <Input
                        id={id}
                        type="email"
                        value={inviteEmail}
                        onChange={(event) => setInviteEmail(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            submitInvite();
                          }
                        }}
                        placeholder="teammate@acme.com"
                        autoComplete="off"
                      />
                    )}
                  </Field>
                  <Field label="Role">
                    {(id) => (
                      <Select
                        id={id}
                        value={inviteRole}
                        onChange={(event) => setInviteRole(event.target.value as AssignableRole)}
                      >
                        {grantableRoles.map((role) => (
                          <option key={role} value={role}>
                            {ROLE_LABEL[role]}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  {inviteError ? (
                    <p role="alert" className="text-sm font-medium text-danger">
                      {inviteError}
                    </p>
                  ) : null}
                  <div className="flex justify-end">
                    <Button
                      icon={<MailPlus className="size-4" />}
                      loading={inviteMutation.isPending}
                      onClick={submitInvite}
                    >
                      Create invite link
                    </Button>
                  </div>
                </>
              )}
            </div>
          </Card>
        ) : null}

        {canManage ? (
          <Card>
            <CardHeader title="Pending invitations" subtitle="Links that haven't been accepted yet." />
            {invitesQuery.isLoading ? (
              <LoadingPanel />
            ) : invites.length === 0 ? (
              <p className="px-5 pb-5 text-sm text-ink-muted">
                No pending invitations — invited links appear here until they're used or revoked.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {invites.map((invite) => (
                  <li key={invite.id} className="flex items-center gap-3 px-5 py-3">
                    <Link2 className="size-4 shrink-0 text-ink-muted" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{invite.email}</p>
                      <p className="text-xs text-ink-muted">
                        Expires {formatDay(invite.expires_at)}
                      </p>
                    </div>
                    <Badge tone={ROLE_BADGE[invite.role]}>{ROLE_LABEL[invite.role]}</Badge>
                    <button
                      type="button"
                      aria-label={`Revoke invitation for ${invite.email}`}
                      onClick={() => revokeMutation.mutate(invite.id)}
                      className={cn(
                        "rounded-lg p-2 text-ink-muted transition hover:bg-danger-soft hover:text-danger",
                        revokeMutation.isPending && "opacity-60",
                      )}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ) : null}
      </div>

      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title="Remove member?"
        description={
          removing
            ? `${removing.full_name || removing.email} loses access immediately and every session is revoked.`
            : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setRemoving(null)}>
              Keep member
            </Button>
            <Button
              variant="danger"
              loading={removeMutation.isPending}
              onClick={() => removing && removeMutation.mutate(removing.id)}
            >
              Remove
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-muted">
          Their transactions stay in the workspace — removing a member never deletes financial
          history.
        </p>
      </Dialog>
    </div>
  );
}
