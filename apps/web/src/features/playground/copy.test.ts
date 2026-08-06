import { describe, expect, it } from "vitest";
import { playgroundCopy } from "./copy";

describe("Playground language", () => {
  it("uses plain-language labels while keeping capability keys available", () => {
    const zh = playgroundCopy("zh-CN");
    expect(zh.route).toBe("要测试的业务能力");
    expect(zh.thread).toBe("会话标识");
    expect(zh.routeName("work_order_ops")).toBe("工单运营");
    expect(zh.routeName("custom_plugin")).toBe("custom_plugin");
    expect(zh.checkName("run_id")).toBe("运行编号是否一致");
  });

  it("keeps the English labels aligned with the Chinese concepts", () => {
    const en = playgroundCopy("en");
    expect(en.route).toBe("Business capability");
    expect(en.inspector).toBe("Run details");
    expect(en.routeName("demo_rag")).toBe("Knowledge search Q&A");
  });
});
