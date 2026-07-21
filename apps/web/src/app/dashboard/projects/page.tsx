"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
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
import { useCreateProject, useProjects, useStyles } from "@/lib/query/hooks";
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
  const { data: styles } = useStyles();
  const createProject = useCreateProject();

  const [title, setTitle] = useState("");
  const [styleId, setStyleId] = useState<string>("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createProject.mutateAsync({
        title,
        target_aspect_ratio: "9:16",
        style_id: styleId || null,
        instructions: instructions || null,
      });
      setTitle("");
      setStyleId("");
      setInstructions("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create project");
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <Card>
        <CardHeader>
          <CardTitle>New project</CardTitle>
          <CardDescription>
            Pick a style and describe what you want -- vertical (9:16) only for now.
          </CardDescription>
        </CardHeader>
        <form onSubmit={onCreate}>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="style">Style</Label>
              <Select value={styleId} onValueChange={(value) => setStyleId(value ?? "")}>
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
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={createProject.isPending || !title}>
              {createProject.isPending ? "Creating..." : "Create project"}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Your projects</h2>
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {projects?.length === 0 && (
          <p className="text-sm text-muted-foreground">No projects yet -- create one above.</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          {projects?.map((project) => (
            <Link key={project.id} href={`/dashboard/projects/${project.id}`}>
              <Card className="transition-colors hover:bg-muted/50">
                <CardHeader>
                  <CardTitle>{project.title}</CardTitle>
                  <CardAction>
                    <Badge variant={STATUS_VARIANT[project.status]}>{project.status}</Badge>
                  </CardAction>
                  {project.instructions && (
                    <CardDescription className="line-clamp-2">
                      {project.instructions}
                    </CardDescription>
                  )}
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
