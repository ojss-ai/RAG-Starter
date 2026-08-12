"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteDocument, fetchDocuments, uploadFile } from "../api";
import type { DocumentRow, UploadResult } from "../types";

const PAGE_SIZE = 20;

export interface UseDocuments {
  documents: DocumentRow[];
  total: number;
  page: number;
  pages: number;
  query: string;
  setQuery: (q: string) => void;
  setPage: (p: number) => void;
  remove: (id: string) => Promise<void>;
  upload: (files: FileList | File[]) => Promise<UploadResult[]>;
  refresh: () => Promise<void>;
}

export function useDocuments(): UseDocuments {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [query, setQueryState] = useState("");

  const refresh = useCallback(async () => {
    const list = await fetchDocuments(query, page * PAGE_SIZE, PAGE_SIZE);
    setDocuments(list.documents);
    setTotal(list.total);
  }, [query, page]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setQuery = useCallback((q: string) => {
    setQueryState(q);
    setPage(0);
  }, []);

  const remove = useCallback(
    async (id: string) => {
      await deleteDocument(id);
      await refresh();
    },
    [refresh],
  );

  const upload = useCallback(
    async (files: FileList | File[]) => {
      const results: UploadResult[] = [];
      for (const file of Array.from(files)) {
        results.push(await uploadFile(file));
      }
      await refresh();
      return results;
    },
    [refresh],
  );

  return {
    documents,
    total,
    page,
    pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
    query,
    setQuery,
    setPage,
    remove,
    upload,
    refresh,
  };
}
