package hu.synostream.android;
import android.app.*;import android.graphics.Color;import android.view.*;import android.widget.*;import org.json.*;import java.util.*;import java.util.concurrent.*;
/** NAS delete review; it never writes before an explicit confirmation. */
final class DeleteUi {
 final MainActivity a;final SynoApp s;final Library.Card card;final Dialog detail;Dialog dialog;TextView status,preview;Button confirm,cancel;LinearLayout seasons;
 final Map<Integer,CheckBox> boxes=new TreeMap<>();MediaDeletion inventory;MediaDeletion.Plan plan;NasClient client;String owner;int epoch;JSONObject library;boolean writing=false,finished=false,attempted=false;Future<?> job;
 DeleteUi(MainActivity activity,Library.Card item,Dialog parent){a=activity;s=a.s;card=item;detail=parent;}
 boolean current(){return s.client==client&&s.epoch==epoch&&s.identity.equals(owner);}
 void show(){
  if(s.demo||s.client==null){a.toast(a.getString(R.string.delete_need_nas));return;}
  if(s.metadataBusy||s.downloadBusy){a.toast(a.getString(R.string.delete_wait));return;}
  client=s.client;owner=s.identity;epoch=s.epoch;library=s.selected();if(library==null)return;
  try{library=new JSONObject(library.toString());}catch(JSONException invalid){return;}
  s.metadataBusy=true;dialog=a.screenDialog();LinearLayout body=a.column();body.setPadding(a.dp(16),0,a.dp(16),a.dp(12));
  body.addView(a.dialogBar(a.getString(R.string.delete_media_title),()->{if(!writing)dialog.dismiss();}),a.lp(-1,52));
  body.addView(a.text(card.title,20,MainActivity.TEXT));body.addView(a.text(a.getString(R.string.delete_media_notice),14,MainActivity.MUTED));
  seasons=a.column();ScrollView seasonScroll=new ScrollView(a);seasonScroll.addView(seasons);body.addView(seasonScroll,a.lp(-1,card.movie?0:160));seasonScroll.setVisibility(card.movie?View.GONE:View.VISIBLE);
  preview=a.text("",13,MainActivity.TEXT);preview.setTextIsSelectable(true);ScrollView scroll=new ScrollView(a);scroll.addView(preview);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
  status=a.text(a.getString(R.string.delete_preparing),14,MainActivity.MUTED);body.addView(status,a.lp(-1,-2));
  LinearLayout buttons=new LinearLayout(a);confirm=a.button(a.getString(R.string.delete_media_title),this::confirm);confirm.setTextColor(0xffeb909b);confirm.setId(R.id.confirm_media_delete);confirm.setEnabled(false);
  cancel=a.button(a.getString(R.string.msg_cancel_b3e118),()->{if(!writing)dialog.dismiss();});buttons.addView(confirm,new LinearLayout.LayoutParams(0,a.dp(56),1));buttons.addView(cancel,a.lp(-2,56));body.addView(buttons);
  dialog.setOnDismissListener(d->{if(!writing){finished=true;if(job!=null)job.cancel(true);release();if(attempted&&current())s.scan(library);}});a.showScreen(dialog,body);
  List<String> seeds=card.movie?List.of(card.path):(card.episodeRoots.isEmpty()?List.of(card.path):List.copyOf(card.episodeRoots));List<String> roots=LibraryConfig.paths(library);List<String> protectedPaths=new ArrayList<>();
  Set<String> members=new HashSet<>(card.memberPaths.isEmpty()?List.of(card.path):card.memberPaths);
  for(Library.Card other:s.rawCards)if(!members.contains(other.path)){for(String p:other.episodeRoots.isEmpty()?List.of(other.path):other.episodeRoots)if(!seeds.contains(p))protectedPaths.add(p);}
  job=s.detail.submit(()->{try{MediaDeletion value=new MediaDeletion(seeds,roots,card.movie,client::listForDeletion,protectedPaths);s.main.post(()->{if(!current()||finished||!dialog.isShowing())return;inventory=value;
    if(!card.movie)for(int season:value.seasons){CheckBox box=new CheckBox(a);box.setText(season==0?a.getString(R.string.delete_specials):a.getString(R.string.delete_season,season));box.setTextColor(MainActivity.TEXT);box.setChecked(value.seasons.size()==1);box.setOnCheckedChangeListener((b,checked)->update());seasons.addView(box);boxes.put(season,box);}update();});}
   catch(Exception error){s.main.post(()->fail(error));}});
 }
 void update(){try{Set<Integer> selected=new TreeSet<>();for(Map.Entry<Integer,CheckBox> entry:boxes.entrySet())if(entry.getValue().isChecked())selected.add(entry.getKey());plan=inventory.plan(card.movie?null:selected);preview.setText(a.getString(R.string.delete_preview_format,String.join("\n",plan.files),a.getString(R.string.delete_empty_folders),String.join("\n",plan.folders)));status.setText(a.getString(R.string.delete_file_count,plan.files.size()));confirm.setEnabled(true);}catch(Exception error){plan=null;confirm.setEnabled(false);status.setText(UiText.message(a,SynoApp.safeError(error)));}}
 void confirm(){if(plan==null||writing||finished||!current()||!dialog.isShowing())return;confirm.setEnabled(false);if(s.scanRunning){status.setText(a.getString(R.string.delete_wait));s.main.postDelayed(this::confirm,300);return;}
  writing=true;attempted=true;s.busy=true;cancel.setEnabled(false);dialog.setCancelable(false);for(CheckBox box:boxes.values())box.setEnabled(false);status.setText(a.getString(R.string.delete_running));MediaDeletion.Plan approved=plan;
  job=s.detail.submit(()->{try{MediaDeletion.Result result=inventory.execute(approved,client::deleteMediaPaths);s.main.post(()->{if(!current()){writing=false;finished=true;release();if(dialog.isShowing())dialog.dismiss();return;}try{Future<?> saved=s.commitMediaDeletion(card,library,result);s.worker.execute(()->{try{if(saved!=null)saved.get();s.main.post(()->success(result));}catch(Exception error){s.main.post(()->fail(error));}});}catch(Exception error){fail(error);}});}catch(Exception error){s.main.post(()->fail(error));}});
 }
 void success(MediaDeletion.Result result){writing=false;finished=true;release();if(detail!=null&&detail.isShowing())detail.dismiss();if(dialog.isShowing())dialog.dismiss();if(current()){a.toast(a.getString(R.string.delete_complete));s.scan(library);}}
 void fail(Exception error){if(finished)return;writing=false;confirm.setEnabled(false);cancel.setEnabled(true);dialog.setCancelable(true);status.setText(UiText.message(a,SynoApp.safeError(error)));release();}
 void release(){if(current()){s.metadataBusy=false;if(attempted)s.busy=false;}}
}
