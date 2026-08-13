import { describe, expect, it } from "vitest";
import { playgroundCopy } from "./copy";

describe("Playground language", () => {
  it("uses plain-language labels while keeping capability keys available", () => {
    const zh = playgroundCopy("zh-CN");
    expect(zh.request).toBe("业务插件测试");
    expect(zh.route).toBe("选择业务插件");
    expect(zh.pluginPurpose).toBe("当前插件作用");
    expect(zh.routePrompt("demo_rag")).toContain("SOP");
    expect(zh.thread).toBe("会话标识");
    expect(zh.routeName("work_order_ops")).toBe("工单运营");
    expect(zh.routeName("custom_plugin")).toBe("custom_plugin");
    expect(zh.checkName("run_id")).toBe("运行编号是否一致");
  });

  it("keeps the English labels aligned with the Chinese concepts", () => {
    const en = playgroundCopy("en");
    expect(en.route).toBe("Choose business plugin");
    expect(en.inspector).toBe("Run details");
    expect(en.routeName("demo_rag")).toBe("Knowledge search Q&A");
    expect(en.routePrompt("demo_rag")).toContain("Search");
  });
});
