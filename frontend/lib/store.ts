import { create } from "zustand";

type WizardDraft = {
  jd_text: string;
  hours_per_day: number;
};

type Store = {
  jobId: string | null;
  draft: WizardDraft;
  approvalNote: string;
  quizMode: boolean;
  setJobId: (id: string | null) => void;
  setDraft: (d: Partial<WizardDraft>) => void;
  setApprovalNote: (n: string) => void;
  setQuizMode: (q: boolean) => void;
};

export const useStore = create<Store>((set) => ({
  jobId: null,
  draft: { jd_text: "", hours_per_day: 3 },
  approvalNote: "",
  quizMode: false,
  setJobId: (jobId) => set({ jobId }),
  setDraft: (d) => set((s) => ({ draft: { ...s.draft, ...d } })),
  setApprovalNote: (approvalNote) => set({ approvalNote }),
  setQuizMode: (quizMode) => set({ quizMode }),
}));
