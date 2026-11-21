package hu.synostream.android;
import android.app.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Explicit user-selected correction, local first and shared on NAS when writable. */
final class MetadataUi {
    private final MainActivity a;private final SynoApp s;
    MetadataUi(MainActivity activity){a=activity;s=a.s;}
    void show(Library.Card card,Dialog detail){
        if(s.demo||s.client==null){a.toast(a.getString(R.string.msg_sign_in_to_edit_metadata_4b0a55));return;}
        if(s.metadataBusy){a.toast(a.getString(R.string.msg_wait_for_metadata_to_finish_saving_ee3494));return;}
        Dialog dialog=a.screenDialog();LinearLayout root=a.column();root.addView(a.dialogBar(a.getString(R.string.msg_add_media_information_333a5f),dialog::dismiss),a.lp(-1,52));
        LinearLayout row=new LinearLayout(a);EditText query=new EditText(a);query.setId(R.id.metadata_query);query.setSingleLine(true);query.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH|android.view.inputmethod.EditorInfo.IME_FLAG_NO_EXTRACT_UI);query.setTextColor(MainActivity.TEXT);query.setHintTextColor(MainActivity.MUTED);query.setHint(a.getString(R.string.msg_title_or_imdb_id_95a3f9));query.setText(card.title);row.addView(query,new LinearLayout.LayoutParams(0,a.dp(52),1));
        Button search=a.button(a.getString(R.string.msg_search_5d2577),()->{});search.setId(R.id.metadata_search);row.addView(search,a.lp(104,52));root.addView(row);
        TextView status=a.text(a.getString(R.string.msg_select_the_correct_movie_or_tv_show_f56bd4),14,MainActivity.MUTED);status.setPadding(a.dp(16),a.dp(8),a.dp(16),a.dp(8));root.addView(status,a.lp(-1,-2));
        ListView results=new ListView(a);results.setId(R.id.metadata_results);root.addView(results,new LinearLayout.LayoutParams(-1,0,1));List<JSONObject> hits=new ArrayList<>();
        search.setOnClickListener(v->{
            ((android.view.inputmethod.InputMethodManager)a.getSystemService(android.content.Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(query.getWindowToken(),0);query.clearFocus();
            String value=query.getText().toString().trim();if(value.isEmpty()){query.setError(a.getString(R.string.msg_enter_a_title_38e915));return;}
            search.setEnabled(false);status.setText(a.getString(R.string.msg_searching_35795f));hits.clear();results.setAdapter(null);
            s.detail.execute(()->{try{
                String key=s.store.secret("tmdb_key");if(key.isBlank())throw new java.io.IOException(a.getString(R.string.msg_enter_your_tmdb_api_key_in_settings_first_a8fb49));
                TmdbApi api=new TmdbApi(key,new MetadataCache(a));Map<Long,JSONObject> candidates=new LinkedHashMap<>();
                if(value.matches("(?i)tt\\d{7,10}")){JSONObject found=new Recognition(api).imdb(value.toLowerCase(Locale.ROOT),card.movie);if(found!=null)candidates.put(found.getLong("id"),found);}
                else{
                    MediaLogic.Name name=MediaLogic.clean(value,false);
                    for(String language:List.of("hu-HU","en-US"))for(String title:MediaLogic.titleVariants(name.title)){
                        JSONArray rows=api.get("search/"+(card.movie?"movie":"tv"),Map.of("query",title,"language",language)).optJSONArray("results");
                        if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject hit=rows.optJSONObject(i);if(hit!=null&&hit.optLong("id")>0)candidates.putIfAbsent(hit.optLong("id"),hit);}
                    }
                }
                s.main.post(()->{if(a.isDestroyed()||!dialog.isShowing())return;hits.addAll(candidates.values());results.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_list_item_1,hits.stream().map(h->h.optString(card.movie?"title":"name")+"  •  "+h.optString(card.movie?"release_date":"first_air_date")).toArray(String[]::new)));status.setText(hits.isEmpty()?a.getString(R.string.msg_no_results_try_another_title_or_imdb_id_04b9d6):hits.size()+a.getString(R.string.msg_results_tap_the_correct_one_12ad44));search.setEnabled(true);});
            }catch(Exception e){s.main.post(()->{if(!a.isDestroyed()&&dialog.isShowing()){status.setText(SynoApp.safeError(e));search.setEnabled(true);}});}});
        });
        results.setOnItemClickListener((parent,view,index,id)->{
            if(s.metadataBusy)return;s.metadataBusy=true;results.setEnabled(false);search.setEnabled(false);status.setText(a.getString(R.string.msg_saving_metadata_db0aff));
            long chosen=hits.get(index).optLong("id");JSONObject library=s.selected();int generation=s.epoch;NasClient client=s.client;
            s.detail.execute(()->{try{
                JSONObject info=new Recognition(new TmdbApi(s.store.secret("tmdb_key"),new MetadataCache(a))).details(chosen,card.movie);if(info==null)throw new java.io.IOException(a.getString(R.string.msg_the_selected_metadata_is_no_longer_available_7aebd0));
                List<String> paths=card.movie?List.of(card.path):card.episodeRoots.isEmpty()?List.of(card.path):card.episodeRoots;
                // Persist the explicit choice before an uncertain network write.
                synchronized(s){for(String path:paths)s.edits.manual(card.movie,path,info);s.store.put("edits:"+s.identity,s.edits.toString());}
                int failed=0;for(String path:paths){String rootPath=library==null?null:LibraryConfig.rootFor(library,path);if(rootPath==null){failed++;continue;}try{client.savePairing(rootPath,path,card.movie,info);s.edits.synced(card.movie,path);}catch(Exception unavailable){failed++;}}
                final int failures=failed;s.main.post(()->{if(s.epoch!=generation)return;s.metadataBusy=false;s.updatedInfo(card,info);if(!a.isDestroyed()){boolean visible=dialog.isShowing()&&detail.isShowing();dialog.dismiss();if(visible){detail.dismiss();a.showDetail(card);}a.toast(failures==0?a.getString(R.string.msg_metadata_saved_to_the_nas_fd382c):a.getString(R.string.msg_the_correction_has_been_saved_on_this_device__202dba));}});
            }catch(Exception e){s.main.post(()->{s.metadataBusy=false;if(!a.isDestroyed()&&dialog.isShowing()){status.setText(SynoApp.safeError(e));search.setEnabled(true);results.setEnabled(true);}});}});
        });
        query.setOnEditorActionListener((view,action,event)->{search.performClick();return true;});a.showScreen(dialog,root);
    }
}
