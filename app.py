import streamlit as st
import pandas as pd
import json
from statsbombpy import sb
import matplotlib.pyplot as plt
from mplsoccer import Pitch
from deep_translator import GoogleTranslator

@st.cache_data
def translate_names(name_list):
    translator = GoogleTranslator(source='en', target='ko')
    translated_dict = {}
    for name in name_list:
        try:
            translated_dict[name] = translator.translate(name)
        except:
            translated_dict[name] = name 
    return translated_dict

st.set_page_config(page_title="찬빈's 패스맵 대시보드", page_icon="⚽", layout="wide")

st.title("⚽ 인터랙티브 축구 패스 네트워크 대시보드")
st.markdown("**한국디지털미디어고등학교 해킹방어과 3510 류찬빈**")
st.divider()

if 'events_df' not in st.session_state:
    st.session_state.events_df = None
if 'match_info' not in st.session_state:
    st.session_state.match_info = None

with st.sidebar:
    st.header("📂 데이터 불러오기")
    data_source = st.radio("데이터 수집 방식 선택:", ["오픈 API (무료 데이터)", "내 JSON 파일 업로드"])
    st.divider()

    if data_source == "오픈 API (무료 데이터)":
        st.write("🔍 **StatsBomb 무료 데이터 탐색기**")
        try:
            comps = sb.competitions()
            comp_options = comps['competition_name'] + " (" + comps['season_name'] + ")"
            selected_comp_str = st.selectbox("1. 대회 및 시즌을 선택하세요:", comp_options.tolist())
            
            selected_row = comps[comp_options == selected_comp_str].iloc[0]
            c_id, s_id = selected_row['competition_id'], selected_row['season_id']
            
            matches = sb.matches(competition_id=c_id, season_id=s_id)
            match_options = matches['home_team'] + " vs " + matches['away_team'] + " (" + matches['match_date'].astype(str) + ")"
            selected_match_str = st.selectbox("2. 경기를 선택하세요:", match_options.tolist())
            
            selected_match_row = matches[match_options == selected_match_str].iloc[0]
            match_id = selected_match_row['match_id']
            
            if st.button("선택한 경기 가져오기"):
                with st.spinner("서버에서 데이터를 당겨오는 중입니다... ⏳"):
                    st.session_state.events_df = sb.events(match_id=match_id)
                    st.session_state.match_info = {
                        'home_team': selected_match_row['home_team'], 'away_team': selected_match_row['away_team'],
                        'home_score': selected_match_row['home_score'], 'away_score': selected_match_row['away_score'],
                        'competition': selected_comp_str, 'date': selected_match_row['match_date']
                    }
                    st.success("데이터 로드 성공!")
        except Exception as e:
            st.error("데이터 목록을 불러오는 중 오류가 발생했습니다.")

    elif data_source == "내 JSON 파일 업로드":
        uploaded_file = st.file_uploader("StatsBomb 포맷 JSON 파일을 올려주세요", type=["json"])
        if uploaded_file is not None:
            data = json.load(uploaded_file)
            st.session_state.events_df = pd.json_normalize(data)
            
            df = st.session_state.events_df
            teams = df['team'].dropna().unique().tolist()
            if len(teams) >= 2:
                goals = df[(df['type'] == 'Shot') & (df['shot_outcome'] == 'Goal')]
                st.session_state.match_info = {
                    'home_team': teams[0], 'away_team': teams[1],
                    'home_score': len(goals[goals['team'] == teams[0]]), 'away_score': len(goals[goals['team'] == teams[1]]),
                    'competition': "업로드된 JSON 데이터", 'date': "알 수 없음"
                }
            st.success("파일 업로드 완료!")

if st.session_state.events_df is not None:
    df = st.session_state.events_df
    team_list = df['team'].dropna().unique().tolist()

    if st.session_state.match_info:
        info = st.session_state.match_info
        st.markdown(f"<p style='text-align: center; color: gray; margin-bottom: 0px;'>{info['competition']} | {info['date']}</p>", unsafe_allow_html=True)
        col_s1, col_s2, col_s3 = st.columns([2, 1, 2])
        with col_s1: st.markdown(f"<h2 style='text-align: right;'>{info['home_team']}</h2>", unsafe_allow_html=True)
        with col_s2: st.markdown(f"<h1 style='text-align: center; color: #ea6969; margin-top: 0px;'>{info['home_score']} : {info['away_score']}</h1>", unsafe_allow_html=True)
        with col_s3: st.markdown(f"<h2 style='text-align: left;'>{info['away_team']}</h2>", unsafe_allow_html=True)
        st.divider()

    st.subheader("🕸️ 팀별 패스 네트워크 분석")
    col_u1, col_u2 = st.columns([1, 1])
    with col_u1: selected_team = st.selectbox("분석할 팀을 선택하세요:", team_list)
    with col_u2: min_pass = st.slider("최소 패스 연결 횟수 (선 굵기 기준):", 1, 10, 3)

    team_df = df[df['team'] == selected_team].copy()
    starting_xi = team_df[team_df['type'] == 'Starting XI']
    pos_priority = {'GK': 0, 'CB': 1, 'LB': 2, 'RB': 3, 'LCB': 1, 'RCB': 1, 'LWB': 2, 'RWB': 3, 'DM': 4, 'CDM': 4, 'LDM': 4, 'RDM': 4, 'CM': 5, 'LCM': 5, 'RCM': 5, 'LM': 6, 'RM': 7, 'AM': 8, 'CAM': 8, 'LAM': 8, 'RAM': 8, 'LW': 9, 'RW': 10, 'CF': 11, 'ST': 11, 'LS': 11, 'RS': 11}
    
    lineup_info = []
    jersey_numbers = {}
    player_names_en = []

    if not starting_xi.empty:
        tactics = starting_xi.iloc[0].get('tactics', {})
        lineup = tactics.get('lineup', []) if isinstance(tactics, dict) else starting_xi.iloc[0].get('tactics.lineup', [])
        if isinstance(lineup, list):
            for player in lineup:
                p_name, p_num, p_pos_full = player['player']['name'], player['jersey_number'], player['position']['name']
                p_pos_short = 'GK' if p_pos_full.lower() == 'goalkeeper' else "".join([word[0].upper() for word in p_pos_full.split()])
                lineup_info.append({"등번호": p_num, "포지션": p_pos_short, "이름": p_name, "priority": pos_priority.get(p_pos_short, 99)})
                jersey_numbers[p_name] = p_num
                player_names_en.append(p_name)

    ko_name_dict = {}
    if player_names_en:
        ko_name_dict = translate_names(player_names_en)

    def draw_passmap(data, team_name, jersey_dict, min_p):
        team_df = data[data['team'] == team_name].copy()
        subs = team_df[team_df['type'] == 'Substitution']
        first_sub_minute = subs['minute'].min() if not subs.empty else 90
        
        passes = team_df[(team_df['type'] == 'Pass') & (team_df['minute'] < first_sub_minute)].copy()
        successful_passes = passes[passes['pass_outcome'].isna()].copy() if 'pass_outcome' in passes.columns else passes.copy()
            
        successful_passes = successful_passes.dropna(subset=['location', 'pass_recipient'])
        successful_passes['x'] = successful_passes['location'].apply(lambda loc: loc[0])
        successful_passes['y'] = successful_passes['location'].apply(lambda loc: loc[1])
        
        average_locs = successful_passes.groupby('player').agg({'x': 'mean', 'y': 'mean'}).reset_index()
        pass_counts = successful_passes.groupby(['player', 'pass_recipient']).size().reset_index(name='pass_count')
        
        pitch = Pitch(pitch_type='statsbomb', pitch_color='#1a1a1a', line_color='#7c7c7c')
        fig, ax = pitch.draw(figsize=(10, 7))
        fig.set_facecolor('#1a1a1a')
        
        for _, row in pass_counts[pass_counts['pass_count'] >= min_p].iterrows():
            passer, recipient, count = row['player'], row['pass_recipient'], row['pass_count']
            if passer in average_locs['player'].values and recipient in average_locs['player'].values:
                start_x = average_locs[average_locs['player'] == passer]['x'].values[0]
                start_y = average_locs[average_locs['player'] == passer]['y'].values[0]
                end_x = average_locs[average_locs['player'] == recipient]['x'].values[0]
                end_y = average_locs[average_locs['player'] == recipient]['y'].values[0]
                pitch.lines(start_x, start_y, end_x, end_y, lw=count*0.5, color='#00ff41', zorder=1, ax=ax, alpha=0.5)
        
        pitch.scatter(average_locs['x'], average_locs['y'], s=700, color='#ff4b4b', edgecolors='white', linewidth=2, zorder=2, ax=ax)
        for _, row in average_locs.iterrows():
            player_name = row['player']
            display_text = str(jersey_dict.get(player_name, "??"))
            pitch.annotate(display_text, xy=(row['x'], row['y']), c='white', va='center', ha='center', size=14, fontweight='bold', zorder=3, ax=ax)
        
        ax.set_title(f"[{team_name}] Pass Network (Min Passes: {min_p})", color='white', fontsize=20, pad=20)
        return fig

    if st.button("패스맵 분석 및 라인업 조회"):
        with st.spinner("로스터 번역 및 패스맵을 생성하는 중입니다... 🌐"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = draw_passmap(df, selected_team, jersey_numbers, min_pass)
                st.pyplot(fig)
                
            with col2:
                st.write(f"📋 **{selected_team} 선발 라인업**")
                if lineup_info:
                    lineup_df = pd.DataFrame(lineup_info).sort_values(by="priority")
                    lineup_df['한글 이름'] = lineup_df['이름'].map(ko_name_dict).fillna(lineup_df['이름'])
                    st.table(lineup_df[["등번호", "포지션", "한글 이름"]])

            st.divider()
            st.subheader(f"🏆 {selected_team} 핵심 선수 스탯 (전체 시간 기준)")
            
            team_passes = team_df[team_df['type'] == 'Pass'].copy()
            successful_team_passes = team_passes[team_passes['pass_outcome'].isna()].copy() if 'pass_outcome' in team_passes.columns else team_passes.copy()
            
            pass_attempts = team_passes.groupby('player').size().reset_index(name='attempts')
            pass_success = successful_team_passes.groupby('player').size().reset_index(name='success')
            
            player_stats = pd.merge(pass_attempts, pass_success, on='player', how='left').fillna(0)
            player_stats['accuracy'] = (player_stats['success'] / player_stats['attempts']) * 100
            
            if 'pass_shot_assist' in team_passes.columns:
                key_passes = team_passes[team_passes['pass_shot_assist'] == True].groupby('player').size().reset_index(name='key_passes')
                player_stats = pd.merge(player_stats, key_passes, on='player', how='left').fillna(0)
            else:
                player_stats['key_passes'] = 0
                
            if not player_stats.empty:
                top_passer = player_stats.sort_values(by='success', ascending=False).iloc[0]
                qualified_passers = player_stats[player_stats['attempts'] >= 20]
                most_accurate = qualified_passers.sort_values(by='accuracy', ascending=False).iloc[0] if not qualified_passers.empty else top_passer
                top_key_passer = player_stats.sort_values(by='key_passes', ascending=False).iloc[0]

                st.markdown("""
                <style>
                [data-testid="stMetricValue"] {
                    font-size: 20px !important;
                    word-wrap: break-word !important;
                    white-space: normal !important;
                }
                </style>
                """, unsafe_allow_html=True)

                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric(label="👑 패스 마스터 (최다 성공)", value=ko_name_dict.get(top_passer['player'], top_passer['player']), delta=f"{int(top_passer['success'])}회 성공")
                with col_m2:
                    st.metric(label="🎯 정교한 발끝 (성공률 1위)", value=ko_name_dict.get(most_accurate['player'], most_accurate['player']), delta=f"{most_accurate['accuracy']:.1f}% (20회 이상 시도)")
                with col_m3:
                    st.metric(label="🔑 플레이메이커 (키패스 1위)", value=ko_name_dict.get(top_key_passer['player'], top_key_passer['player']), delta=f"{int(top_key_passer['key_passes'])}회 창출")

else:
    st.info("👈 왼쪽 사이드바에서 대회와 경기를 선택하고 데이터를 불러와 주세요!")
