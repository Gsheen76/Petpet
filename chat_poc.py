"""Command-line chat with Sheen — verify AI persona before integrating.

Usage:
  1. Get a Zhipu API key at https://open.bigmodel.cn (free, GLM-4.7-Flash)
  2. Set it:  set ZHIPU_API_KEY=your.key.here   (PowerShell: $env:ZHIPU_API_KEY="...")
     OR create config.json:  {"api_key": "your.key.here"}
  3. Run:     python chat_poc.py

Type to chat. Commands:
  /reset   clear memory
  /show    show what Sheen remembers
  /quit    exit
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Sheen_ai as ai

def print_streaming(text):
    sys.stdout.write(text)
    sys.stdout.flush()

def main():
    print("=" * 52)
    print("  Sheen — 你的陪伴小狗  (GLM-4.7-Flash, 智谱)")
    print("=" * 52)

    if not ai.get_api_key():
        print("\n⚠  还没设置 API key。两种方式：")
        print("   1) PowerShell:  $env:ZHIPU_API_KEY=\"你的key\"")
        print('   2) 在 desktop-pet 文件夹建 config.json:  {"api_key":"你的key"}')
        print("\n没 key 也能试，Sheen 会用预设话术回复（不是真 AI）。")
    else:
        print("\n✓ 检测到 API key，已连接智谱 GLM-4.7-Flash。")

    print(f"\nSheen: {ai.time_greeting()}")
    print("-" * 52)
    print("输入你要说的话，回车发送。/quit 退出\n")

    mem = ai.load_memory()

    while True:
        try:
            user = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSheen: 拜拜主人，记得想我汪~")
            break

        if not user:
            continue
        if user == "/quit":
            print("Sheen: 拜拜主人，记得想我汪~")
            break
        if user == "/reset":
            mem = ai._default_memory()
            ai.save_memory(mem)
            print("Sheen: 嗯？我好像忘了很多事…重新认识你吧！汪~")
            continue
        if user == "/show":
            print(f"[记忆] 主人档案: {mem.get('user_profile','（空）')}")
            print(f"[记忆] 对话轮数: {len(mem.get('history',[]))}")
            continue

        # stream the reply
        sys.stdout.write("Sheen: ")
        full = []
        err = None
        for kind, payload in ai.chat_stream(user, mem=mem, on_token=print_streaming):
            if kind == "token":
                full.append(payload)
            elif kind == "done":
                full = [payload]
                break
            elif kind == "error":
                err = payload
                break
        if err:
            reply = ai.fallback_reply(user, err)
            print(reply)
            full = [reply]
        else:
            print()  # newline after stream

        # save to memory
        ai.append_history(mem, "user", user)
        ai.append_history(mem, "assistant", "".join(full))


if __name__ == "__main__":
    main()
