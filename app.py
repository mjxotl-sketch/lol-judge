import streamlit as st
import google.generativeai as genai
import time
import tempfile
import base64
import requests
import random

# 1. 웹사이트 스타일 및 테마 설정
st.set_page_config(page_title="롤 전적 분석기: 솔랭 정의구현 심판소", layout="centered")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    .stApp {
        background-color: #1a1c1e; 
        background-image: 
            linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
        background-size: 50px 50px; 
        color: #e2e8f0;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Noto Sans KR', sans-serif !important;
    }
    
    .logo-wrapper {
        display: flex; justify-content: center; align-items: center; width: 100%; margin-top: 25px; margin-bottom: 25px;
    }
    
    .court-logo-box {
        display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
        background-color: #26292b; border: 3px double #e2e8f0; padding: 30px 40px; border-radius: 6px;
        box-shadow: 0px 12px 30px rgba(0, 0, 0, 0.7); max-width: 680px; width: 100%;
    }
    
    .logo-row { display: flex; align-items: center; justify-content: center; width: 100%; gap: 25px; }
    .scale-icon { font-size: 55px !important; filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.5)); }
    .logo-title-top { font-size: 42px !important; font-weight: 800 !important; color: #ffffff !important; letter-spacing: 4px; }
    .logo-title-bottom { font-size: 46px !important; font-weight: 800 !important; color: #ffffff !important; letter-spacing: 8px; margin-top: 8px; }
    .court-subtitle { color: #ffffff !important; font-size: 16px; font-weight: 600; margin-top: 22px; line-height: 1.7; }
    .section-title { font-weight: 700; color: #e2e8f0; margin-top: 25px; margin-bottom: 12px; font-size: 19px; }

    .stTextArea textarea, .stTextInput input {
        background-color: #2d3136 !important; color: #ffffff !important; border: 2px solid #4b5563 !important; border-radius: 4px !important;
    }

    .deeplol-select-box { background-color: #202224; border: 2px solid #4b5563; border-radius: 4px; padding: 15px; margin-bottom: 15px; }
    .stat-card { background: #202224; border: 1px solid #4b5563; border-radius: 6px; padding: 15px; text-align: center; }
    .court-box { background-color: #26292b; border-left: 8px double #e2e8f0; border-right: 8px double #e2e8f0; border-top: 2px solid #4b5563; border-bottom: 2px solid #4b5563; padding: 35px; margin-top: 35px; line-height: 1.8; }

    .stButton>button {
        width: 100%; background: linear-gradient(to bottom, #4b5563 0%, #1f2937 100%) !important; color: #e2e8f0 !important;
        font-weight: 700 !important; padding: 16px !important; font-size: 19px !important; letter-spacing: 3px;
    }
    </style>
""", unsafe_allow_html=True)

# 헤더 출력
st.markdown("""
    <div class="logo-wrapper">
        <div class="court-logo-box">
            <div class="logo-row">
                <div class="scale-icon">⚖️</div>
                <div class="title-text-container">
                    <div class="logo-title-top">솔랭 정의구현</div>
                    <div class="logo-title-bottom">심판소</div>
                </div>
                <div class="scale-icon">⚖️</div>
            </div>
            <div class="court-subtitle">라이엇 공식 API 배동 및 실시간 인게임 전적 파싱 시스템<br>배포 버전 환경 구축 완료.</div>
        </div>
    </div>
""", unsafe_allow_html=True)
st.write("---")

# API 설정 (배포 시 환경변수나 실제 키로 교체 가능)
GOOGLE_API_KEY = "AIzaSyBAgzNsLMk-hd1RhwdNHjcmOPOPFc9VMVg"
genai.configure(api_key=GOOGLE_API_KEY)

# 💡 라이엇 공식 API 인증 키 (실제 배포 시 여기에 본인의 Riot API Key를 넣으시면 됩니다)
# 81번 줄을 이렇게 바꾸세요
riot_api_key = st.secrets.get("RIOT_API_KEY", "")

if "recorded_video_bytes" not in st.session_state:
    st.session_state.recorded_video_bytes = None

# [라이엇 공식 실시간 데이터 통신 엔진]
def get_real_riot_data(summoner_name, tag_line, api_key):
    """ 라이엇 아시아 서버에 직접 요청해 실제 매치 스태츠를 가져오는 함수 """
    if not api_key:
        return None
    
    headers = {"X-Riot-Token": api_key}
    try:
        # 1. Account-v1 API로 puuid 조회
        account_url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tag_line}"
        acc_res = requests.get(account_url, headers=headers, timeout=4)
        if acc_res.status_code != 200: return None
        puuid = acc_res.json().get("puuid")
        
        # 2. Match-v5 API로 최근 게임 1개 ID 조회
        match_list_url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
        match_res = requests.get(match_list_url, headers=headers, timeout=4)
        if match_res.status_code != 200 or not match_res.json(): return None
        last_match_id = match_res.json()[0]
        
        # 3. Match 상세 정보 조회 및 내 스태츠 파싱
        match_detail_url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{last_match_id}"
        detail_res = requests.get(match_detail_url, headers=headers, timeout=4)
        if detail_res.status_code != 200: return None
        
        participants = detail_res.json().get("info", {}).get("participants", [])
        for p in participants:
            if p.get("puuid") == puuid:
                kills = p.get("kills", 0)
                deaths = p.get("deaths", 1)
                assists = p.get("assists", 0)
                kda = round((kills + assists) / max(deaths, 1), 2)
                damage = p.get("totalDamageDealtToChampions", 0)
                win = "승리" if p.get("win") else "패배"
                champion = p.get("championName", "Unknown")
                
                return {"kda": kda, "damage": damage, "champion": champion, "win": win, "real": True}
    except Exception:
        return None
    return None

# 3. 전적 입력창 (DeepLoL 스타일 실전 분리형)
st.markdown("<div class='section-title'>🔍 피고인 라이엇 ID 입력 (DeepLoL 서치 엔진)</div>", unsafe_allow_html=True)
col_name, col_tag = st.columns([3, 1])
with col_name:
    summoner_input = st.text_input("소환사명 입력", placeholder="예: 하이드 온 부시", label_visibility="collapsed")
with col_tag:
    tag_input = st.text_input("태그 입력", placeholder="KR1", label_visibility="collapsed")

final_data_text = ""
selected_account_name = ""

if summoner_input and tag_input:
    selected_account_name = f"{summoner_input}#{tag_input}"
    
    with st.spinner("🌐 라이엇 공식 메인프레임 서버에서 전적 실시간 파싱 중..."):
       real_data = get_real_riot_data(summoner_input, tag_input, riot_api_key)
    
    # 실제 라이엇 데이터 연동 성공 시
    if real_data and real_data.get("real"):
        kda_val = real_data["kda"]
        avg_deal = real_data["damage"]
        champ_name = real_data["champion"]
        outcome = real_data["win"]
        troll_index = random.randint(75, 99) if kda_val < 1.2 else random.randint(25, 60)
        
        st.success(f"🎯 실제 존재하는 소환사 확인 완료! 최근 매치 플레이 챔피언: {champ_name} ({outcome})")
        final_data_text = f"[라이엇 실시간 데이터 - 소환사: {selected_account_name}, 최근 매치 챔피언: {champ_name}, 결과: {outcome}, 실제 KDA: {kda_val}, 아군 오인 사격 피해량: {avg_deal}, 트롤 위험도: {troll_index}%]"
    
    # 라이엇 키가 없거나 실패 시 배포 환경 방어용 정밀 시뮬레이션 작동
    else:
        # 닉네임을 시드로 고정하여 고유한 티어와 지표 매칭
        random.seed(sum(ord(c) for c in selected_account_name))
        tiers = ["DIAMOND II", "EMERALD IV", "PLATINUM I", "GOLD III", "CHALLENGER"]
        selected_tier = random.choice(tiers)
        kda_val = round(random.uniform(0.5, 1.8), 2)
        troll_index = random.randint(65, 98)
        avg_deal = random.randint(4200, 11500)
        
        if not RIOT_API_KEY:
            st.info("💡 데모 모드 작동 중 (사이드바에 라이엇 API 키를 입력하면 100% 진짜 인게임 전적과 교체됩니다).")
        else:
            st.warning("⚠️ 입력하신 소환사명과 태그를 라이엇 서버에서 찾을 수 없어 가상 매칭 전적으로 대체합니다.")
            
        final_data_text = f"[라이엇 동기화 데이터 - 소환사: {selected_account_name}, 등록 티어: {selected_tier}, 최근 20게임 평균 KDA: {kda_val}, 트롤 성향 지수: {troll_index}%, 평균 딜량: {avg_deal}]"
        champ_name = "최근 모스트 챔피언"

    # 대시보드 렌더링
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='stat-card'><span style='color:#cbd5e1; font-size:13px;'>최근 인게임 KDA</span><br><b style='font-size:22px; color:#ffffff;'>{kda_val}</b></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='stat-card'><span style='color:#ef4444; font-size:13px;'>트롤 위험 지수</span><br><b style='font-size:22px; color:#ef4444;'>{troll_index}%</b></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='stat-card'><span style='color:#3b82f6; font-size:13px;'>챔피언 가한 피해량</span><br><b style='font-size:22px; color:#ffffff;'>{avg_deal}</b></div>", unsafe_allow_html=True)

st.write("")

# 4. 정황 기술서 및 증거 비디오 팩터
st.markdown("<div class='section-title'>📜 사건 정황 고발서 (필수)</div>", unsafe_allow_html=True)
situation = st.text_area(
    "사건의 정황을 왜곡 없이 상세히 기술하십시오.",
    placeholder="예: 팀원들이랑 싸우더니 템 다 팔고 우물에서 감정표현만 갈아댑니다. 인게임 지표랑 같이 선고해 주세요.",
    height=90, label_visibility="collapsed"
)

st.markdown("<div class='section-title'>📹 영상 증거: 협곡 블랙박스 캡처/녹화 제어 (선택)</div>", unsafe_allow_html=True)
recorded_data = st.text_input("video_data_bridge", label_visibility="collapsed", key="js_video_bridge")

st.components.v1.html("""
    <div style="display: flex; gap: 15px; justify-content: center; align-items: center; background:#2d3136; padding: 15px; border-radius: 6px; border: 2px solid #4b5563; font-family: sans-serif;">
        <button id="startBtn" style="padding: 12px 24px; background: #dc2626; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size:15px;">🎥 협곡 화면 캡처 녹화 시작</button>
        <button id="stopBtn" style="padding: 12px 24px; background: #4b5563; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size:15px;" disabled>🛑 녹화 종료 및 제출</button>
        <span id="statusLabel" style="color: #cbd5e1; font-size: 14px;">🔴 대기 중</span>
    </div>

    <script>
        let mediaRecorder; let recordedChunks = [];
        const startBtn = document.getElementById('startBtn'); const stopBtn = document.getElementById('stopBtn'); const statusLabel = document.getElementById('statusLabel');
        startBtn.onclick = async () => {
            recordedChunks = [];
            try {
                const stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: "window" }, audio: true });
                mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm; codecs=vp9' });
                mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data); };
                mediaRecorder.onstop = async () => {
                    statusLabel.innerText = "⏳ 인코딩 및 심판소 전송 중...";
                    const blob = new Blob(recordedChunks, { type: 'video/webm' });
                    const reader = new FileReader(); reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        const base64data = reader.result.split(',')[1];
                        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                        if(inputs.length > 0) {
                            inputs[0].value = base64data; inputs[0].dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        statusLabel.innerText = "✅ 전송 완료! 아래 재판 개정 버튼을 누르세요.";
                    };
                    stream.getTracks().forEach(track => track.stop());
                };
                mediaRecorder.start(1000); startBtn.disabled = true; stopBtn.disabled = false; statusLabel.innerText = "⏺️ 협곡 화면 녹화 중...";
            } catch (err) { statusLabel.innerText = "❌ 취소됨"; }
        };
        stopBtn.onclick = () => { mediaRecorder.stop(); startBtn.disabled = false; stopBtn.disabled = true; };
    </script>
""", height=90)

if recorded_data:
    st.session_state.recorded_video_bytes = base64.b64decode(recorded_data)
    st.success("🎯 증거 영상 캡처본이 심판소 중앙 컴퓨터에 동기화되었습니다!")
    with st.expander("🎥 녹화된 증거 블랙박스 보기"):
        st.video(st.session_state.recorded_video_bytes)

# 5. 최종 판결 선고
if st.button("🔨 재판 개정 (판결 선고 요청)"):
    if not situation:
        st.error("❗ 고발서가 비어 있습니다. 정황을 적어주십시오.")
    elif not selected_account_name:
        st.error("❗ 피고인의 닉네임과 태그를 정확히 입력해 주십시오.")
    else:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        stages = [
            "🏛️ 심판소 대리석 법정 개정 및 증거 목록 검토 완료",
            "📊 라이엇 공식 매치 로그 테이블 교차 검증 중...",
            "👁️ AI 판사가 멀티모달 비디오 프레임을 정밀 추적하는 중...",
            "🔨 솔랭 정의구현 특별법에 의거한 판결문 각인 중..."
        ]
        
        for i, stage in enumerate(stages):
            status_text.markdown(f"<p style='color: #e2e8f0; font-family: \"Pretendard\"; font-weight: bold; text-align: center; font-size: 16px;'>{stage}</p>", unsafe_allow_html=True)
            progress_bar.progress((i + 1) * 25)
            time.sleep(0.6)
            
        status_text.empty()
        progress_bar.empty()

        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            base_prompt = f"""
            당신은 롤 유저들의 상한 멘탈을 완벽히 대변하는 '솔랭 정의구현 심판소 냉혈한 부장판사'입니다.
            라이엇 데이터베이스 조회를 통해 확보한 공식 스태츠 지표를 기반으로, 엄숙하면서도 피도 눈물도 없는 극강의 매운맛 팩트 폭행 판결문을 선고하십시오.
            
            [라이엇 공식 조회 전적 스펙]
            {final_data_text}

            출력 형식 포맷을 엄격하게 준수하십시오:
            ## 📜 [주문] 극독의 선고 판결문
            
            ### 👨‍⚖️ 1. 사건의 요지 및 라이엇 데이터 판독
            (피고인의 정확한 라이엇 ID를 호명하고, 조회된 실제 티어와 처참한 KDA 수치, 한심한 딜량을 조목조목 들이대며 과학적인 트롤러임을 팩폭할 것)
            
            ### ⚖️ 2. 과실 책임 비율
            - 고발인(원고) 책임: X%
            - 피고인(상대방) 책임: Y%
            
            ### 🔨 3. 양형 이유 및 판사의 극독 일침
            (이 트롤러가 협곡 생태계에 끼친 해악을 엄벌하며, 기상천외하고 코믹한 독한 형벌 제시)
            """
            
            contents = [base_prompt, f"유저의 상황 진술: {situation}"]
            
            if st.session_state.recorded_video_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
                    tmp.write(st.session_state.recorded_video_bytes)
                    tmp_path = tmp.name
                uploaded_video = genai.upload_file(path=tmp_path)
                while uploaded_video.state.name == "PROCESSING":
                    time.sleep(1)
                    uploaded_video = genai.get_file(uploaded_video.name)
                contents.append(uploaded_video)
            
            with st.spinner("AI 부장판사가 라이엇 실시간 매치 데이터와 영상을 융합 심리 중입니다..."):
                response = model.generate_content(contents)
            
            st.markdown(f"""
                <div class="court-box">
                    <h3 style="color: #e2e8f0; text-align: center; margin-bottom: 25px; font-weight: bold; letter-spacing: 2px;">👨‍⚖️ 판 결 선 고 (실전 배포형)</h3>
                    {response.text}
                </div>
            """, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"⚠️ 재판 중 돌발 오류가 발생했습니다: {e}")
