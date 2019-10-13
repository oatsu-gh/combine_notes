#!/usr/bin/python3
# coding: utf-8
"""
ピッチ曲線で音程を保持しつつ音符を結合するスクリプト
"""
import sys
from pprint import pprint

# from pysnooper import snoop


TEST = True


def read_txt(filepath):
    """
    UTAUの一時データから必要な情報を読み取る。
    リストの要素を持つ辞書型を返す。
    """

    d = {'Tempo': 60, 'Length': [], 'Lyric': [], 'NoteNum': [],
         'PBW': [], 'PBY': [], 'PBS': [], 'NEXT_PBS': 0}

    # ファイルをリストとして読み込む（改行コード削除）
    with open(filepath, 'r+') as f:
        lines = [s.strip() for s in f.readlines()]

    tag = ''    # 行の属性判定管理
    for line in lines:
        # 行の属性情報を登録する
        if line.startswith('[#'):
            tag = line

        # 選択範囲ノートの情報行である場合
        elif tag not in ['[#VERSION]', '[#SETTING]', '[#PREV]', '[#NEXT]']:
            # 長さを読み取る
            if line.startswith('Length='):
                d['Length'].append(int(line[7:]))
            # 歌詞を読み取る
            elif line.startswith('Lyric='):
                d['Lyric'].append(line[6:])
            # 音階番号を読み取る
            elif line.startswith('NoteNum='):
                d['NoteNum'].append(int(line[8:]))
            # PBSを読み取ってリストで辞書に格納
            elif line.startswith('PBS='):
                d['PBS'].append(int(line.split(';')[0][4:]))
            # PBWを読み取ってリストで辞書に格納
            elif line.startswith('PBW='):
                d['PBW'].append(list(map(float, line[4:].split(','))))
            # PBYを読み取ってリストで辞書に格納
            elif line.startswith('PBY='):
                d['PBY'].append(list(map(float, line[4:].split(','))))

        # NEXTの歌詞
        elif tag == '[#NEXT]' and line.startswith('Lyric='):
            next_lyric = line[6:]

        # NEXTが休符でないときはNEXTのPBSを読み取る
        # NEXTが休符のときはNEXTのPBSは0のまま
        elif tag == '[#NEXT]' and line.startswith('PBS=') and next_lyric != 'R':
            d['NEXT_PBS'] = int(line.split(';')[0][4:])

        # テンポを読み取る
        elif tag == '[#SETTING]' and line.startswith('Tempo='):
            d['Tempo'] = float(line[6:])

        # 必要ない情報はスルー
        else:
            pass
    print('UTAU一時ファイル読み取り完了')
    return d, lines


def length_msec(tempo, length_ticks):
    """
    Tempo[beat/min] 480[Ticks/beat] を用いて、
    Length[Ticks] → Length[msec] の変換をする。
    """
    # sec_per_beat = 60 / tempo
    # ticks_per_beat = 480
    # sec_per_ticks = sec_per_beat / tick_per_beat
    # msec_per_ticks = sec_per_ticks * 1000
    # 以上をまとめると msec_per_ticks = int(1000 * 60 / 480 / tempo)
    # length_msec = length_ticks * msec_per_ticks
    # return int(length_msec)
    return int(125 * length_ticks // tempo)


def combine_length(d):
    """
    ノート長さを合算する。
    """
    combined_length = sum(d['Length'])
    print('Length結合完了 combined_length:', combined_length)
    return combined_length


def combine_pbw(d):
    """
    PBWを一つにまとめる。
    PBSに起因する点の位置に注意
    Length[Ticks] と PBW[msec] の単位変換が必要なことに注意
    終端のピッチ点のタイミングに注意
    """
    # 辞書から値の読み出し
    lengths = d['Length']
    next_pbs = d['NEXT_PBS']
    pbss = d['PBS']
    pbws = d['PBW']
    tempo = d['Tempo']

    # まとめたPBW用リスト
    combined_pbw = []

    # ノート数
    num_note = len(lengths)

    for n in range(num_note):
        # 先頭ノートはとくに何もしない
        if n == 0:
            # まとめPBWに追記
            combined_pbw += pbws[n]

        # 先頭以外のノートはピッチ点位置（時刻）を計算してずらす
        # また、左側PBSの部分を組み込む必要がある
        elif n != num_note - 1:
            # 前のノートの音程維持用のピッチ点（ポルタメント開始位置に相当）を追加
            combined_pbw.append(
                length_msec(tempo, lengths[n - 1]) - pbss[n - 1] - sum(pbws[n - 1]) + pbss[n])
            # まとめPBWに追記
            combined_pbw += pbws[n]

        # 最終ノートは選択範囲外との接続のためのピッチ点の処理が必要
        elif n == num_note - 1:
            # 前のノートの音程維持用のピッチ点（ポルタメント開始位置に相当）を追加
            combined_pbw.append(
                length_msec(tempo, lengths[n - 1]) - pbss[n - 1] - sum(pbws[n - 1]) + pbss[n])

            # NEXTのPBS点まで音程を維持するためのピッチ点を追加
            pbws[n].append(length_msec(tempo, lengths[n]) - pbss[n] - sum(pbws[n]) + next_pbs)
            pbws[n].append(0.0)

            # まとめPBWに追記
            combined_pbw += pbws[n]

    print('PBW結合完了    combined_pbw:', combined_pbw)
    return combined_pbw


def combine_pby(d):
    """
    PBYを一つにまとめる。
    PBSに相当するピッチ点は前のノート音高依存なことに注意
    """
    nns = d['NoteNum']
    pbys = d['PBY']

    # まとめたPBY用リスト
    combined_pby = []

    # ノート数
    num_note = len(nns)

    # 各ノートのPBYを調製して追加していく
    for n in range(num_note):
        # 先頭ノートはピッチシフトの必要がない
        if n == 0:
            pbys[n].append(0.0)
            # まとめPBYに追記
            combined_pby += pbys[n]

        # それ以降は先頭ノートの音高に応じてピッチシフトが必要
        elif n != num_note - 1:
            # 音程の差をピッチ差に変換
            height_distance = (nns[0] - nns[n]) * (-10.0)
            # 音程を維持するためのピッチ点を追加
            pbys[n].append(0.0)
            # 先頭ノート音高に合わせてピッチシフト
            pbys[n] = list(map(lambda x: x + height_distance, pbys[n]))
            # まとめPBYに追記
            combined_pby += pbys[n]

        # 末尾のノートだけ処理が増える
        else:
            # 音程の差をピッチ差に変換
            height_distance = (nns[0] - nns[n]) * (-10.0)
            # 音程を維持するためのピッチ点を追加
            pbys[n].append(0.0)
            # 先頭ノート音高に合わせてピッチシフト
            pbys[n] = list(map(lambda x: x + height_distance, pbys[n]))
            # 選択範囲外のノートにつなげるためのピッチ点を追加
            pbys[n].append(0.0)
            # まとめPBYに追記
            combined_pby += pbys[n]

    print('PBY結合完了    combined_pby:', combined_pby)
    return combined_pby


def edit_lines(lines, d):
    """
    計算結果をまとめて、書き込むデータを整理する関数。
    ・不要ノート削除
    ・先頭ノートのデータ置き換え
    """
    # 先頭ノート情報かどうか判定用のフラグ
    # 4のときのみ先頭ノートであると判定
    flag = 0

    # 書き換え後データ用のリスト
    edited_lines = []
    # このリストに格納するデータを文字列にしておく
    length = str(d['Length'])
    pbw = ','.join(str(v) for v in d['PBW'])
    pby = ','.join(str(v) for v in d['PBY'])

    # 各要素（行）を読み取って新規リストに追記
    for line in lines:
        # 先頭ノートまではタグの出現回数を記録
        if line.startswith('[#'):
            flag += 1

        # 先頭ノートのときは一部の値を置き換える
        if flag == 4:
            if line.startswith('Length='):
                edited_lines.append('Length=' + length)
            elif line.startswith('PBW='):
                edited_lines.append('PBW=' + pbw)
            elif line.startswith('PBY='):
                edited_lines.append('PBY=' + pby)
            else:
                edited_lines.append(line)

        # 選択範囲のうち、先頭以外のノートは削除
        elif (flag > 4) and line.startswith('[#') and not line == '[#NEXT]':
            edited_lines.append('[#DELETE]')

        # タグ行や先頭ノートの情報以外はそのまま転載
        else:
            edited_lines.append(line)

    print('データ整理完了')
    return edited_lines


def overwrite_txt(filepath, lines):
    """
    生成したデータをテキスト文字列でファイル出力する関数。
    """
    with open(filepath, mode='w') as f:
        f.write('\n'.join(lines))
    print('UTAU一時ファイル上書き完了')


def main():
    """
    全体の処理を実行する関数。
    """
    # UTAU一時ファイルを指定
    filepath = sys.argv[1]
    # UTAU一時ファイル読み取り・一部ノート削除
    d, original_lines = read_txt(filepath)
    if TEST:
        print('\n----- original_lines -----')
        pprint(original_lines)
        print('--------------------------\n')
    print('\n----- d-------------------')
    pprint(d)
    print('--------------------------\n')

    # 休符にはピッチの情報がなく、ノート処理がずれるため中断
    if 'R' in d['Lyric']:
        print('\n** ERROR ****')
        print('休符を含んでいます。音符にしてポルタメントを付与してからやり直してください。')
        input('Press entes to exit.')
        sys.exit()
    # ノート長を合算
    combined_length = combine_length(d)
    # PBWを統合
    combined_pbw = combine_pbw(d)
    # PBYを統合
    combined_pby = combine_pby(d)

    # 計算結果を辞書にまとめる
    combined_data = {'Length': combined_length, 'PBW': combined_pbw, 'PBY': combined_pby}

    # 計算結果のリストをもとにデータを書き換える
    edited_lines = edit_lines(original_lines, combined_data)
    if TEST:
        print('\n----- edited_lines -----')
        pprint(edited_lines)
        print('--------------------------\n')

    # 整理したデータでファイルを上書き保存
    overwrite_txt(filepath, edited_lines)


if __name__ == '__main__':
    main()
    input('Press enter to exit.')
