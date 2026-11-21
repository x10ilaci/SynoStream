package hu.synostream.android;
import android.app.*;
import android.graphics.Color;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Full-height phone detail; one playback action and Windows-style corner actions. */
final class DetailUi {
    private final MainActivity a;private final SynoApp s;
    DetailUi(MainActivity activity){a=activity;s=a.s;}
    void show(Library.Card card){if(!card.movie){new SeriesUi(a,this).show(card);return;}
        Dialog dialog=a.screenDialog();FrameLayout screen=new FrameLayout(a);screen.setBackgroundColor(Color.BLACK);LinearLayout root=a.column();root.setBackgroundColor(Color.BLACK);screen.addView(root,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout bar=a.dialogBar("",dialog::dismiss);bar.setBackgroundColor(Color.TRANSPARENT);
        View info=a.icon("info",a.getString(R.string.msg_add_media_information_333a5f),()->new MetadataUi(a).show(card,dialog));info.setId(R.id.detail_info);bar.addView(info,a.lp(48,48));
        View hide=a.icon("hide",a.getString(R.string.msg_exclude_from_library_keep_the_file_7f7f95),()->hide(card,dialog));hide.setId(R.id.detail_hide);bar.addView(hide,a.lp(48,48));View trash=a.icon("trash",a.getString(R.string.delete_media_title),()->new DeleteUi(a,card,dialog).show());trash.setId(R.id.detail_delete);trash.setEnabled(!s.demo&&s.client!=null);bar.addView(trash,a.lp(48,48));
        if(!card.movie){View merge=a.icon("merge",a.getString(R.string.msg_merge_with_another_tv_show_card_602fa0),()->merge(card,dialog));merge.setId(R.id.detail_merge);bar.addView(merge,a.lp(48,48));if(!card.manualGroupId.isEmpty()){View unmerge=a.icon("remove",a.getString(R.string.msg_undo_manual_merge_493cb9),()->{s.edits.unmerge(card.manualGroupId);s.saveEdits();dialog.dismiss();a.invalidatePage();});unmerge.setId(R.id.detail_unmerge);bar.addView(unmerge,a.lp(48,48));}}
        boolean landscape=a.getResources().getConfiguration().screenWidthDp>a.getResources().getConfiguration().screenHeightDp;
        LinearLayout content=a.column();content.setBackgroundColor(Color.BLACK);
        int heroHeight=landscape?156:320;
        FrameLayout hero=new FrameLayout(a);ImageView backdrop=new ImageView(a);backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);Library.Card imageCard=new Library.Card(card.path,card.title,card.movie);imageCard.poster=card.backdrop.isEmpty()?card.poster:card.backdrop;a.poster(backdrop,imageCard);hero.addView(backdrop,new FrameLayout.LayoutParams(-1,-1));View gradient=new View(a);gradient.setBackground(new android.graphics.drawable.GradientDrawable(android.graphics.drawable.GradientDrawable.Orientation.TOP_BOTTOM,new int[]{0x66000000,0x00000000,0xff000000}));hero.addView(gradient,new FrameLayout.LayoutParams(-1,-1));content.addView(hero,a.lp(-1,heroHeight));
        LinearLayout summary=new LinearLayout(a);summary.setGravity(Gravity.CENTER_VERTICAL);summary.setPadding(a.dp(20),a.dp(16),a.dp(20),a.dp(12));FrameLayout cover=new FrameLayout(a);cover.setPadding(a.dp(3),a.dp(3),a.dp(3),a.dp(3));cover.setBackgroundColor(Color.WHITE);ImageView poster=new ImageView(a);poster.setScaleType(ImageView.ScaleType.CENTER_CROP);a.poster(poster,card);cover.addView(poster,new FrameLayout.LayoutParams(-1,-1));
        Button play=a.button("▶",()->{});play.setId(R.id.play_button);play.setTextColor(Color.WHITE);play.setTextSize(28);play.setGravity(Gravity.CENTER);android.graphics.drawable.GradientDrawable circle=new android.graphics.drawable.GradientDrawable();circle.setShape(android.graphics.drawable.GradientDrawable.OVAL);circle.setColor(0xe6985fc4);play.setBackground(circle);play.setMinWidth(0);play.setMinimumWidth(0);play.setPadding(0,0,0,0);FrameLayout.LayoutParams playLp=new FrameLayout.LayoutParams(a.dp(48),a.dp(48),Gravity.CENTER);cover.addView(play,playLp);play.setContentDescription(a.getString(R.string.msg_playback_4f7dc0));play.setEnabled(card.movie);play.setTooltipText(a.getString(R.string.msg_long_press_choose_another_player_7b8f91));summary.addView(cover,a.lp(104,156));
        LinearLayout titles=a.column();titles.setPadding(a.dp(14),0,0,0);TextView title=a.text(card.title,22,MainActivity.TEXT);titles.addView(title,a.lp(-1,-2));TextView date=a.text(card.date+(card.runtime>0?"    ◷ "+(card.runtime/60)+":"+String.format(java.util.Locale.ROOT,"%02d",card.runtime%60):""),16,MainActivity.TEXT);titles.addView(date,a.lp(-1,36));if(card.rating>0){TextView rating=a.text("★".repeat(Math.max(0,Math.min(5,(int)Math.round(card.rating/2))))+"☆".repeat(Math.max(0,5-Math.min(5,(int)Math.round(card.rating/2)))),23,0xffffc107);rating.setContentDescription(a.getString(R.string.msg_tmdb_rating_5edf4e)+String.format(java.util.Locale.ROOT,"%.1f",card.rating)+" / 10");titles.addView(rating,a.lp(-1,30));}summary.addView(titles,new LinearLayout.LayoutParams(0,-2,1));content.addView(summary,a.lp(-1,-2));
        if(!card.genres.isBlank()){TextView genres=a.text(card.genres,16,MainActivity.MUTED);genres.setPadding(a.dp(20),0,a.dp(20),a.dp(8));content.addView(genres,a.lp(-1,-2));}
        TextView overview=a.text(card.overview.isBlank()?a.getString(R.string.msg_no_description_available_6cb1bb):card.overview,16,MainActivity.MUTED);overview.setLineSpacing(a.dp(5),1);overview.setPadding(a.dp(20),a.dp(4),a.dp(20),a.dp(24));content.addView(overview,a.lp(-1,-2));
        ListView episodes=new ListView(a);episodes.setId(R.id.episode_list);episodes.setChoiceMode(ListView.CHOICE_MODE_SINGLE);episodes.setBackgroundColor(Color.BLACK);
        LinearLayout words=content;
        if(card.movie){ScrollView scroll=new ScrollView(a);scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));}
        else {TextView label=a.text(a.getString(R.string.msg_episodes_391bb8),17,MainActivity.TEXT);label.setPadding(a.dp(20),0,0,0);content.addView(label,a.lp(-1,44));episodes.addHeaderView(content,null,false);episodes.setPadding(0,a.dp(52),0,0);episodes.setClipToPadding(true);root.addView(episodes,new LinearLayout.LayoutParams(-1,0,1));}
        screen.addView(bar,new FrameLayout.LayoutParams(-1,a.dp(52),Gravity.TOP));
        final String[] selected={card.movie?card.path:null};
        play.setOnClickListener(v->{if(selected[0]!=null)a.play(selected[0],false);});play.setOnLongClickListener(v->{if(selected[0]!=null)a.play(selected[0],true);return true;});
        if(!card.movie){
            if(s.demo){
                List<NasClient.Entry> sample=new ArrayList<>();for(int i=1;i<=18;i++){NasClient.Entry e=new NasClient.Entry(a.getString(R.string.msg_demo_episode_a8603c),"/demo/episode"+i+".mkv",false,0);e.season=1;e.episode=i;sample.add(e);}populate(episodes,play,selected,sample);
            }else{
                TextView loading=a.text(a.getString(R.string.msg_loading_episodes_10f4c7),13,MainActivity.MUTED);words.addView(loading,a.lp(-1,28));NasClient client=s.client;
                s.detail.execute(()->{try{List<NasClient.Entry> entries=new Library(client,"").episodes(card.episodeRoots.isEmpty()?List.of(card.path):card.episodeRoots);s.main.post(()->{if(!a.isDestroyed()&&dialog.isShowing()){loading.setVisibility(View.GONE);populate(episodes,play,selected,entries);if(entries.isEmpty())loading.setText(a.getString(R.string.msg_no_playable_episodes_c9b10a));if(entries.isEmpty())loading.setVisibility(View.VISIBLE);}});}catch(Exception e){s.main.post(()->{if(!a.isDestroyed()&&dialog.isShowing())loading.setText(UiText.message(a,SynoApp.safeError(e)));});}});
            }
        }
        dialog.setOnDismissListener(d->{if(a.detailCard==card)a.detailCard=null;});a.showScreen(dialog,screen);
    }
    private void populate(ListView list,Button play,String[] selected,List<NasClient.Entry> entries){
        list.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_list_item_single_choice,entries.stream().map(NasClient.Entry::label).toArray(String[]::new)));
        for(int i=0;i<entries.size();i++)if(entries.get(i).path.equals(a.detailEpisodePath)){selected[0]=entries.get(i).path;list.setItemChecked(i+list.getHeaderViewsCount(),true);list.setSelection(i+list.getHeaderViewsCount());play.setEnabled(true);break;}
        list.setOnItemClickListener((p,v,index,id)->{int actual=index-list.getHeaderViewsCount();if(actual<0||actual>=entries.size())return;selected[0]=entries.get(actual).path;a.detailEpisodePath=selected[0];play.setEnabled(true);a.play(selected[0],false);});
    }
    void hide(Library.Card card,Dialog detail){
        new AlertDialog.Builder(a).setTitle(a.getString(R.string.msg_hide_from_library_f2b202)).setMessage(a.getString(R.string.msg_this_card_will_be_hidden_on_this_device_files_ccd2ea)).setNegativeButton(a.getString(R.string.msg_cancel_b3e118),null).setPositiveButton(a.getString(R.string.msg_hide_3f552c),(d,w)->{try{s.edits.hide(card);s.saveEdits();detail.dismiss();a.invalidatePage();}catch(Exception e){a.toast(a.getString(R.string.msg_the_card_could_not_be_hidden_c06139));}}).show();
    }
    void merge(Library.Card source,Dialog detail){
        if(s.busy){a.toast(a.getString(R.string.msg_wait_for_the_scan_to_finish_cc745a));return;}List<Library.Card> targets=new ArrayList<>();for(Library.Card card:s.cards)if(!card.movie&&!card.path.equals(source.path))targets.add(card);
        if(targets.isEmpty()){a.toast(a.getString(R.string.msg_there_is_no_other_series_card_in_this_library_3b47f6));return;}
        new AlertDialog.Builder(a).setTitle(a.getString(R.string.msg_which_series_would_you_like_to_merge_into_c95003)).setItems(targets.stream().map(c->c.title).toArray(String[]::new),(d,index)->{try{s.edits.merge(s.selectedLibrary,source,targets.get(index));s.saveEdits();detail.dismiss();a.invalidatePage();}catch(Exception e){a.toast(a.getString(R.string.msg_the_merge_could_not_be_saved_9d8ad5));}}).setNegativeButton(a.getString(R.string.msg_cancel_b3e118),null).show();
    }
    void restoreHidden(){
        JSONObject hidden=s.edits.hidden();List<String> keys=new ArrayList<>();Iterator<String> iterator=hidden.keys();while(iterator.hasNext())keys.add(iterator.next());
        if(keys.isEmpty()){a.toast(a.getString(R.string.msg_no_hidden_titles_ea8d95));return;}
        List<String> titles=new ArrayList<>();for(String key:keys)if(!titles.contains(hidden.optString(key)))titles.add(hidden.optString(key));
        new AlertDialog.Builder(a).setTitle(a.getString(R.string.msg_which_title_would_you_like_to_restore_c2f670)).setItems(titles.toArray(String[]::new),(d,index)->{String title=titles.get(index);for(String key:new ArrayList<>(keys))if(hidden.optString(key).equals(title))s.edits.restore(key);s.saveEdits();a.invalidatePage();}).setNegativeButton(a.getString(R.string.msg_close_090df7),null).show();
    }
}
