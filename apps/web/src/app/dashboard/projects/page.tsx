"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { useCreateProject, useMyPlan, useProjects, useStyles } from "@/lib/query/hooks";
import type { ProjectStatus } from "@/types/api";

const STATUS_VARIANT: Record<ProjectStatus, "secondary" | "default" | "destructive" | "outline"> = {
  draft: "secondary",
  processing: "default",
  ready: "default",
  failed: "destructive",
  archived: "outline",
};

export default function ProjectsPage() {
  const router = useRouter();
  const { data: projects, isLoading } = useProjects();
  const { data: myPlan } = useMyPlan();
  const { data: styles } = useStyles();
  const createProject = useCreateProject();

  const [title, setTitle] = useState("");
  const [styleId, setStyleId] = useState<string>("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const styleItems = styles?.map((style) => ({ value: style.id, label: style.name })) ?? [];

  const projectCount = projects?.length ?? 0;
  const projectLimit = myPlan?.limits.max_projects;
  const atProjectLimit = projectLimit !== undefined && projectCount >= projectLimit;

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const project = await createProject.mutateAsync({
        title,
        target_aspect_ratio: "9:16",
        style_id: styleId || null,
        instructions: instructions || null,
      });
      router.push(`/dashboard/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create project");
    }
  }

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
        {!showForm && (
          <Button onClick={() => setShowForm(true)} disabled={atProjectLimit}>
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

      {/* New project form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New project</CardTitle>
            <CardDescription>
              Pick a style and describe what you want — vertical (9:16) only for now. You&apos;ll
              upload footage on the next screen.
            </CardDescription>
          </CardHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              onCreate(e);
            }}
            className="flex flex-col gap-4 px-4 pb-4"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="style">Style</Label>
              <Select
                items={styleItems}
                value={styleId}
                onValueChange={(value) => setStyleId(value ?? "")}
              >
                <SelectTrigger id="style" className="w-full">
                  <SelectValue placeholder="Choose a style" />
                </SelectTrigger>
                <SelectContent>
                  {styles?.map((style) => (
                    <SelectItem key={style.id} value={style.id}>
                      {style.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="instructions">Instructions (optional)</Label>
              <Textarea
                id="instructions"
                placeholder='e.g. "Turn this podcast into a punchy hook-driven short."'
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex items-center gap-2">
              <Button type="submit" disabled={createProject.isPending || !title}>
                {createProject.isPending ? "Creating..." : "Create project"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Project list */}
      <div className="flex flex-col gap-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {!isLoading && projects?.length === 0 && !showForm && (
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
            <Button onClick={() => setShowForm(true)} disabled={atProjectLimit}>
              <FolderPlusIcon />
              New project
            </Button>
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
