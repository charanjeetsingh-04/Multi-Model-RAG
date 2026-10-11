"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Upload as UploadIcon, FileVideo } from "lucide-react";
import { apiBaseUrl, getAccess } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  }, [title]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      "video/mp4": [".mp4"],
      "video/quicktime": [".mov"],
      "video/x-matroska": [".mkv"],
      "video/webm": [".webm"]
    }
  });

  async function onSubmit() {
    if (!file) return toast.error("Pick a video first");
    if (!title.trim()) return toast.error("Title is required");
    setUploading(true);
    setProgress(0);

    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title);
    if (description) fd.append("description", description);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiBaseUrl()}/videos/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${getAccess() || ""}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      setUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        toast.success("Uploaded! Processing started.");
        router.push("/library");
      } else {
        toast.error(`Upload failed (${xhr.status})`);
      }
    };
    xhr.onerror = () => { setUploading(false); toast.error("Network error"); };
    xhr.send(fd);
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <Card>
        <CardHeader><CardTitle>Upload a video</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition ${
              isDragActive ? "border-primary bg-accent" : "border-border"
            }`}>
            <input {...getInputProps()} />
            {file ? (
              <div className="space-y-1">
                <FileVideo className="mx-auto w-8 h-8"/>
                <p className="font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
              </div>
            ) : (
              <div className="space-y-1">
                <UploadIcon className="mx-auto w-8 h-8 text-muted-foreground"/>
                <p>Drop a video here or click to select</p>
                <p className="text-xs text-muted-foreground">mp4, mov, mkv, webm</p>
              </div>
            )}
          </div>

          <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />

          {uploading && (
            <div className="w-full h-2 bg-muted rounded">
              <div className="h-2 bg-primary rounded" style={{ width: `${progress}%` }} />
            </div>
          )}

          <Button onClick={onSubmit} disabled={uploading || !file} className="w-full">
            {uploading ? `Uploading… ${progress}%` : "Upload"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
