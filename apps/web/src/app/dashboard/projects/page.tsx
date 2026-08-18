"use client";

import Link from "next/link";
import { ArrowRightIcon, FolderPlusIcon, SparklesIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useMyPlan, useProjects } from "@/lib/query/hooks";
import type { ProjectStatus } from "@/types/api";

const STATUS_VARIANT: Record<ProjectStatus, "secondary" | "default" | "destructive" | "outline"> = {
  draft: "secondary",
  processing: "default",
  ready: "default",
  failed: "destructive",
  archived: "outline",
};

export default function ProjectsPage() {
  const { data: projects, isLoading } = useProjects();
  const { data: myPlan } = useMyPlan();

  const projectCount = projects?.length ?? 0;
  const projectLimit = myPlan?.limits.max_projects;
  const atProjectLimit = projectLimit !== undefined && projectCount >= projectLimit;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {projectLimit !== undefined
              ? `${projectCount} of ${projectLimit} projects used${projectCount === 0 ? " — create your first one" : ""}`
              : "Create a project and upload footage to start editing."}
          </p>
          {projectLimit !== undefined && (
            <div className="mt-3 h-1.5 w-full max-w-60 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${Math.min(100, (projectCount / projectLimit) * 100)}%` }}
              />
            </div>
          )}
        </div>
        {atProjectLimit ? (
          <Button disabled>
            <FolderPlusIcon />
            New project
          </Button>
        ) : (
          <Button render={<Link href="/dashboard/projects/new" />}>
            <FolderPlusIcon />
            New project
          </Button>
        )}
      </div>

      {atProjectLimit && (
        <div className="flex flex-col gap-2 rounded-xl border border-primary/40 bg-primary/[0.07] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5 text-sm">
            <SparklesIcon className="size-4 shrink-0 text-primary" />
            <span>
              You&apos;ve used all {projectLimit} projects on the{" "}
              <span className="capitalize">{myPlan?.tier ?? "free"}</span> plan. Delete one or
              upgrade for more room.
            </span>
          </div>
          <Link href="/pricing">
            <Button size="sm">View plans</Button>
          </Link>
        </div>
      )}

      {/* Project list */}
      <div className="flex flex-col gap-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {!isLoading && projects?.length === 0 && (
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border px-6 py-16 text-center">
            <span className="flex size-12 items-center justify-center rounded-xl border border-border bg-card">
              <FolderPlusIcon className="size-5 text-muted-foreground" />
            </span>
            <div>
              <h2 className="font-medium">No projects yet</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Create your first project to start turning footage into shorts.
              </p>
            </div>
            {atProjectLimit ? (
              <Button disabled>
                <FolderPlusIcon />
                New project
              </Button>
            ) : (
              <Button render={<Link href="/dashboard/projects/new" />}>
                <FolderPlusIcon />
                New project
              </Button>
            )}
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {projects?.map((project) => (
            <Link key={project.id} href={`/dashboard/projects/${project.id}`}>
              <Card className="group transition-colors hover:border-primary/40">
                <CardHeader>
                  <CardTitle className="group-hover:text-primary">{project.title}</CardTitle>
                  <CardAction>
                    <Badge variant={STATUS_VARIANT[project.status]}>{project.status}</Badge>
                  </CardAction>
                  {project.instructions && (
                    <CardDescription className="line-clamp-2">{project.instructions}</CardDescription>
                  )}
                  <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground group-hover:text-primary">
                    Open project
                    <ArrowRightIcon className="size-3.5" />
                  </span>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
