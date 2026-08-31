# -*- coding: utf-8 -*-
"""
徐霞客游记 · VoxCPM 旁白批量生成脚本
=====================================
用途：为「后期万里遐征」动态叙事系统生成 9 段说书人旁白 MP3。

【运行环境】
  1. NVIDIA 显卡（显存 ≥ 8GB），驱动支持 CUDA 12+
  2. Python 3.10 ~ 3.12
  3. 安装依赖：
     pip install voxcpm soundfile
     （首次运行会自动从 HuggingFace 下载 VoxCPM2 模型，约 5GB，需耐心等待；
       国内网络可改用 ModelScope，见下方 USE_MODELSCOPE 开关）

【使用方法】
  python generate_narration.py
  生成结果在 audio_out/ 目录（wav），随后：
     python generate_narration.py --to-mp3   # 需要系统已安装 ffmpeg
  最后把 audio_out/*.mp3 复制到 assets/audio/ 并推送即可。

【音色方案】
  首段用 Voice Design 定制"中年男性说书人"音色（固定 seed 保证可复现），
  之后各段以首段音频为参考做可控克隆，保证九段音色完全一致。
"""

import os
import sys
import argparse

USE_MODELSCOPE = False   # 国内网络下载慢时改为 True
SEED = 42                # 固定随机种子,保证音色可复现
OUT_DIR = "audio_out"

# 说书人音色描述(Voice Design)
VOICE_DESC = "（中年男性说书人，嗓音浑厚沉稳，略带沙哑，吐字从容，有传统评书的抑扬韵味）"

# 九段旁白文案（与 index.html 中 LATE_STORIES 的 narration 保持同步）
SEGMENTS = [
    ("1636-jiangyin",  "崇祯九年秋天，年届五十的徐霞客从江阴出发，与僧人静闻结伴西行。静闻刺血抄写成法华经，发愿送往云南鸡足山。一个为经书，一个为山河，两人就此踏上万里征途。徐霞客说：大丈夫当朝碧海而暮苍梧。"),
    ("1636-minqian",   "入冬之后，路线从浙赣山地折向西南。徐霞客冒雨翻越仙霞岭，一路考察丹霞与岩洞。山路泥泞，脚夫屡屡加价，他据理力争，又把每一笔旅费如实记进日记。行路之难不在山高水长，而在人心曲直。"),
    ("1637-hengzhou",  "崇祯十年二月，深夜的湘江之上突遇强盗。船被烧，行李被抢，静闻为护经书身受刀伤，徐霞客赤足跳入寒江才逃得性命。友人劝他返乡，他答：我荷一锸来，何处不可埋吾骨。在衡州筹得路资后，他继续西行。"),
    ("1637-guilin",    "进入广西，徐霞客以桂林为据点遍历峰林岩洞，对七星岩先后探查十五个洞口，写成最早的洞穴测绘报告。也是在广西，僧人静闻病逝。徐霞客背负他的遗骨与血经，继续西行，不敢因死亡而辜负朋友。"),
    ("1638-guizhou",   "进入贵州，山愈密，路愈险。徐霞客在镇宁白水河见到了黄果树大瀑布，日记里写下：珠帘钩不卷，匹练挂遥峰。他还细察水雾被风吹散、又聚于潭面的景象。别人看瀑布看壮观，他看瀑布看构造。"),
    ("1638-yunnan",    "崇祯十一年秋末，徐霞客进入云南，滇游日记自此开篇。经曲靖、昆明一带，滇池浩渺，山原辽阔。他发现大明一统志所记多处与实地不符，便在日记里直言纠错。地理之学，在他这里是走出来的学问。"),
    ("1639-dali",      "崇祯十二年，徐霞客出大理北上鸡足山，将静闻和尚的遗骨安葬山中，血经供于悉檀寺。两年前的生死之约至此圆满。他又登上鸡足绝顶，观东日、西海、北雪、南云。朋友把他带到了此行最壮阔的高处。"),
    ("1639-tengchong", "徐霞客翻越高黎贡山，抵达腾冲，这是他一生足迹的最西端。他考察打鹰山的火山遗迹，拾起浮石验证石质浮而不沉，又下到硫磺塘热海，见沸泉蒸腾如雾。他以实地见闻推断火山喷发之迹，成为中国火山考察的第一人。万里遐征，至此抵达顶点。"),
    ("1640-finale",    "四年万里，徐霞客历经两度遇盗、三次绝粮，足迹远至云南腾冲。一六四零年，他因足疾被送归江阴，次年病逝家中，年五十五岁。他留下的六十余万字游记，成为中国古代地理学的巅峰。徐霞客的山河之旅，至此暂告一段落。"),
]


def wav_to_mp3(wav_path):
    """有 ffmpeg 则转 mp3 并删除 wav,否则保留 wav 并提示"""
    mp3 = wav_path[:-4] + ".mp3"
    rc = os.system(f'ffmpeg -y -loglevel error -i "{wav_path}" -codec:a libmp3lame -qscale:a 4 "{mp3}"')
    if rc == 0:
        os.remove(wav_path)
        print("  -> mp3:", mp3)
    else:
        print("  ! 未检测到 ffmpeg,保留 wav。请自行转换或直接把 wav 交给我处理。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to-mp3", action="store_true", help="生成后调用 ffmpeg 转 mp3")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    if USE_MODELSCOPE:
        from modelscope import snapshot_download
        model_dir = "./pretrained_models/VoxCPM2"
        if not os.path.isdir(model_dir):
            snapshot_download("OpenBMB/VoxCPM2", local_dir=model_dir)
        model_id = model_dir
    else:
        model_id = "openbmb/VoxCPM2"

    print("加载 VoxCPM2 模型(首次运行需下载约 5GB)...")
    from voxcpm import VoxCPM
    model = VoxCPM.from_pretrained(model_id, load_denoiser=False)

    out_paths = []
    ref_wav = None
    for i, (key, text) in enumerate(SEGMENTS):
        out = os.path.join(OUT_DIR, f"{key}.wav")
        print(f"[{i+1}/{len(SEGMENTS)}] 生成 {key} ...")
        if i == 0:
            # 首段:Voice Design 定制说书人音色(固定 seed)
            wav = model.generate(
                text=VOICE_DESC + text,
                cfg_value=2.0,
                inference_timesteps=10,
                seed=SEED,
            )
        else:
            # 后续段:以首段为参考克隆音色,保证九段音色一致
            wav = model.generate(
                text=text,  # 纯净正文,无前缀
                reference_wav_path=ref_wav,
                cfg_value=2.0,
                inference_timesteps=10,
            )
        import soundfile as sf
        sf.write(out, wav, model.tts_model.sample_rate)
        if ref_wav is None:
            ref_wav = out  # 后续全部克隆首段音色
        out_paths.append(out)
        print("  ->", out)

    # 模块四:徐霞客老者自述(年迈嗓音,control 指令控制,正文无前缀)
    print("[模块四] 生成 value-intro ...")
    wav = model.generate(
        text="老朽徐霞客。三十余年，双屐丈量山河，足迹遍及大半个中国。有人问我，缘何如此执着？徐霞客游记，既是一部地理考察之作，更是一部山水文章——我将风土人情与胸中所感，尽数融入笔端。我又常年深入实地，细察山川地貌、水文岩溶，为后世留存真实的地理。以游记写山河，以足迹探自然，这便是我一生的价值。",
        control_instruction="年迈男性，约八十岁，苍老沙哑的低沉嗓音，语速缓慢，有长者讲述往事的沧桑韵味",
        reference_wav_path=os.path.join(OUT_DIR, "1636-jiangyin.wav"),
        cfg_value=2.4,
        inference_timesteps=10,
    )
    import soundfile as sf
    vp = os.path.join(OUT_DIR, "value-intro.wav")
    sf.write(vp, wav, model.tts_model.sample_rate)
    print("  ->", vp)

    print("\n全部生成完毕!")
    if args.to_mp3:
        for p in out_paths:
            wav_to_mp3(p)
    print("\n下一步:把 audio_out/ 里的 mp3 文件复制到 assets/audio/ 目录。")


if __name__ == "__main__":
    main()
