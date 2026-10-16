package __PACKAGE__;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.*;
import android.hardware.camera2.*;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.widget.*;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.*;
import androidx.camera.core.Camera;
import androidx.camera.camera2.interop.Camera2CameraControl;
import androidx.camera.camera2.interop.Camera2CameraInfo;
import androidx.camera.camera2.interop.CaptureRequestOptions;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.video.*;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;
import com.google.common.util.concurrent.ListenableFuture;
import org.json.*;
import java.io.File;
import java.util.*;
import java.util.concurrent.*;

/** Foreground-only native camera. No static Activity, View or callback references. */
public final class ApkpyCameraActivity extends AppCompatActivity {
    private int BG = Color.rgb(14,18,22), PANEL = Color.rgb(26,32,38), ACCENT = Color.rgb(149,237,199), TEXT=Color.WHITE, ON_ACCENT=BG, MUTED=Color.LTGRAY;
    private static final String DEFAULT_CONTROLS=__CAMERA_UI_CONTROLS__, DEFAULT_LABELS=__CAMERA_UI_LABELS__, DEFAULT_COLORS=__CAMERA_UI_COLORS__;
    private final ArrayList<String> controlOrder=new ArrayList<>();
    private final LinkedHashMap<String,View> controlViews=new LinkedHashMap<>();
    private JSONObject uiLabels;
    private String cameraTitle, controlsPosition;
    private float buttonRadius;
    private ScrollView controlsScroll;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private ProcessCameraProvider provider;
    private Camera camera;
    private Preview preview;
    private ImageCapture photo;
    private VideoCapture<Recorder> video;
    private Recording recording;
    private PreviewView view;
    private FrameLayout stage;
    private LinearLayout body, controls;
    private Overlay overlay;
    private TextView status, shutter, pause, modeButton, lensButton, flashButton, qualityButton, timerButton, zoomLabel, exposureLabel, ratioButton, gridButton, torchButton, audioButton;
    private SeekBar zoomSlider, exposureSlider;
    private String mode, lens, flash, quality, ratio;
    private boolean grid, audio, mirror, busy, paused, torch, ready, done, countdown, recordingStarting, destroyed;
    private int timer, jpegQuality, maxDuration, generation, manualGeneration;
    private float initialZoom;
    private int initialExposure;
    private int manualIso;
    private double shutterMs;
    private float focusDistance;
    private String whiteBalance;
    private File pending;
    private FrameLayout review;
    private VideoView reviewVideo;
    private String resultTag, errorTag;

    public static Bundle options(String... pairs) {
        Bundle b = new Bundle();
        for (int i=0;i+1<pairs.length;i+=2) b.putString(pairs[i],pairs[i+1]);
        return b;
    }
    private String option(String key,String fallback) { String v=getIntent().getStringExtra(key); return v==null?fallback:v; }
    private boolean flag(String key,boolean fallback) { String v=option(key,String.valueOf(fallback)); if (!v.equalsIgnoreCase("true")&&!v.equalsIgnoreCase("false")) throw new IllegalArgumentException(key); return Boolean.parseBoolean(v); }
    private int number(String key,int fallback,int low,int high) { double d=Double.parseDouble(option(key,""+fallback)); if(d<low||d>high||!Double.isFinite(d)||d!=Math.floor(d))throw new IllegalArgumentException(key); return (int)d; }
    private double decimal(String key,double fallback,double low,double high) {double d=Double.parseDouble(option(key,""+fallback));if(!Double.isFinite(d)||d<low||d>high)throw new IllegalArgumentException(key);return d;}
    private String choice(String key,String fallback,String... values) { String s=option(key,fallback); if(!Arrays.asList(values).contains(s))throw new IllegalArgumentException(key); return s; }

    private String label(String key){return uiLabels.optString(key,key);}
    private void readUI() throws Exception {
        JSONArray all=new JSONArray(DEFAULT_CONTROLS), selected=new JSONArray(option("controls",DEFAULT_CONTROLS));
        HashSet<String> allowed=new HashSet<>();for(int i=0;i<all.length();i++)allowed.add(all.getString(i));
        for(int i=0;i<selected.length();i++){Object value=selected.get(i);if(!(value instanceof String)||!allowed.contains(value)||controlOrder.contains(value))throw new IllegalArgumentException("controls: unknown or duplicate control");controlOrder.add((String)value);}
        if(!controlOrder.contains("close")||!controlOrder.contains("shutter"))throw new IllegalArgumentException("controls must include close and shutter");
        uiLabels=new JSONObject(DEFAULT_LABELS);JSONObject customLabels=new JSONObject(option("labels","{}"));
        for(Iterator<String> keys=customLabels.keys();keys.hasNext();){String key=keys.next();Object value=customLabels.get(key);if(!uiLabels.has(key)||!(value instanceof String)||!validCaption((String)value))throw new IllegalArgumentException("labels: "+key);uiLabels.put(key,value);}
        JSONObject palette=new JSONObject(DEFAULT_COLORS), customColors=new JSONObject(option("colors","{}"));
        for(Iterator<String> keys=customColors.keys();keys.hasNext();){String key=keys.next();Object value=customColors.get(key);if(!palette.has(key)||!(value instanceof String)||!((String)value).matches("#[0-9a-fA-F]{6}"))throw new IllegalArgumentException("colors: "+key);palette.put(key,value);}
        BG=Color.parseColor(palette.getString("background"));PANEL=Color.parseColor(palette.getString("surface"));ACCENT=Color.parseColor(palette.getString("accent"));TEXT=Color.parseColor(palette.getString("text"));ON_ACCENT=Color.parseColor(palette.getString("on_accent"));MUTED=Color.parseColor(palette.getString("muted"));
        cameraTitle=option("title","CAMERA");if(!validCaption(cameraTitle))throw new IllegalArgumentException("title");
        controlsPosition=choice("controls_position","auto","auto","top","bottom");buttonRadius=(float)decimal("button_radius",18,0,32);
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        int flags=0;if(androidx.core.graphics.ColorUtils.calculateLuminance(BG)>.5){flags|=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;if(Build.VERSION.SDK_INT>=26)flags|=View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;}getWindow().getDecorView().setSystemUiVisibility(flags);
    }
    private boolean validCaption(String value){return !value.trim().isEmpty()&&value.codePointCount(0,value.length())<=48&&!value.matches("(?s).*[\\x00-\\x1F].*");}

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        // Back leaves with "cancelled", not with nothing. Through the dispatcher:
        // an app that targets Android 16 is no longer handed onBackPressed() there.
        getOnBackPressedDispatcher().addCallback(this,new androidx.activity.OnBackPressedCallback(true){
            @Override public void handleOnBackPressed(){cancel();}
        });
        if(saved!=null&&saved.getBundle("cameraOptions")!=null)getIntent().putExtras(saved.getBundle("cameraOptions"));
        resultTag=option("resultCallback",""); errorTag=option("errorCallback","");
        setResult(RESULT_CANCELED, answer("", "cancelled"));
        if (getSupportActionBar()!=null) getSupportActionBar().hide();
        getWindow().setStatusBarColor(BG); getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(0);
        try {
            mode=choice("mode","photo","photo","video"); lens=choice("lens","back","back","front");
            flash=choice("flash","off","off","on","auto"); quality=choice("quality","fhd","sd","hd","fhd","uhd");
            ratio=choice("aspect_ratio","4:3","4:3","16:9");
            grid=flag("grid",true); audio=flag("audio",true); mirror=flag("mirror",true);
            timer=number("timer",0,0,30); maxDuration=number("max_duration",60,1,3600);
            jpegQuality=number("jpeg_quality",95,1,100); initialExposure=number("exposure",0,-20,20);
            initialZoom=Float.parseFloat(option("zoom","1"));
            if(!Float.isFinite(initialZoom)||initialZoom<1||initialZoom>100)throw new IllegalArgumentException("zoom");
            manualIso=number("iso",0,0,51200);shutterMs=decimal("shutter_ms",0,0,1000);focusDistance=(float)decimal("focus_distance",-1,-1,100);
            whiteBalance=choice("white_balance","auto","auto","daylight","cloudy","incandescent","fluorescent");
            if((manualIso==0)!=(shutterMs==0)||(focusDistance<0&&focusDistance!=-1))throw new IllegalArgumentException("manual controls");
            readUI();
        } catch(Exception e) { finishResult(false,"", "invalid_options: "+e.getMessage()); return; }
        createUI();
        if(saved!=null && saved.getString("pending")!=null) {
            File f=new File(saved.getString("pending"));
            if(f.isFile() && f.getParentFile().equals(new File(getFilesDir(),"apkpy_camera"))) {pending=f; showReview(); return;}
        }
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED) startProvider();
        else requestPermissions(new String[]{Manifest.permission.CAMERA},901);
    }
    private int dp(float n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}
    private TextView text(String s,int size,int color){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);t.setGravity(Gravity.CENTER);return t;}
    private TextView button(String s,Runnable action) {
        TextView t=text(s,13,TEXT);t.setPadding(dp(10),dp(8),dp(10),dp(8)); t.setMinHeight(dp(48));
        t.setTextColor(new android.content.res.ColorStateList(new int[][]{new int[]{android.R.attr.state_enabled},new int[]{}},new int[]{TEXT,MUTED}));
        android.graphics.drawable.GradientDrawable bg=new android.graphics.drawable.GradientDrawable();bg.setColor(PANEL);bg.setCornerRadius(dp(buttonRadius));t.setBackground(bg);
        t.setContentDescription(s);t.setOnClickListener(v->action.run());t.setFocusable(true);return t;
    }
    private LinearLayout row(){LinearLayout r=new LinearLayout(this);r.setOrientation(LinearLayout.HORIZONTAL);r.setGravity(Gravity.CENTER_VERTICAL);return r;}
    private void cell(LinearLayout row,android.view.View v){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);p.setMargins(dp(3),dp(4),dp(3),dp(4));row.addView(v,p);}
    private void createUI(){
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(BG);
        // The camera owns one inset path, including Android 15 edge-to-edge.
        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(root,(v,insets)->{
            androidx.core.graphics.Insets i=insets.getInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars()|androidx.core.view.WindowInsetsCompat.Type.displayCutout());
            v.setPadding(i.left,i.top,i.right,i.bottom);return insets;
        });
        LinearLayout header=row();cell(header,button(label("close"),()->cancel()));
        TextView title=text(cameraTitle,14,ACCENT);cell(header,title);if(controlOrder.contains("pro"))cell(header,button(label("pro"),()->pro()));else cell(header,text("",14,TEXT));root.addView(header,new LinearLayout.LayoutParams(-1,-2));
        body=new LinearLayout(this);root.addView(body,new LinearLayout.LayoutParams(-1,0,1));
        stage=new FrameLayout(this);view=new PreviewView(this);view.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);view.setScaleType(PreviewView.ScaleType.FIT_CENTER);
        stage.setBackgroundColor(Color.BLACK);stage.addView(view,new FrameLayout.LayoutParams(-1,-1));
        overlay=new Overlay();stage.addView(overlay,new FrameLayout.LayoutParams(-1,-1));
        controls=new LinearLayout(this);controls.setOrientation(LinearLayout.VERTICAL);controls.setPadding(dp(10),0,dp(10),dp(8));
        status=text("Opening camera…",12,ACCENT);status.setPadding(dp(8),dp(6),dp(8),dp(6));controls.addView(status);
        LinearLayout settings=row();
        flashButton=button("",()->choose(label("flash"),new String[]{"off","on","auto"},v->{flash=v;applyFlash();refreshLabels();}));cell(settings,flashButton);
        timerButton=button("",()->choose(label("timer"),new String[]{"0","3","5","10"},v->{timer=Integer.parseInt(v);refreshLabels();}));cell(settings,timerButton);
        gridButton=button("",()->{grid=!grid;overlay.invalidate();refreshLabels();});cell(settings,gridButton);controls.addView(settings);
        LinearLayout second=row();
        qualityButton=button("",()->choose(label("quality"),new String[]{"sd","hd","fhd","uhd"},v->{quality=v;bind();}));cell(second,qualityButton);
        ratioButton=button("",()->choose(label("ratio"),new String[]{"4:3","16:9"},v->{ratio=v;bind();}));cell(second,ratioButton);
        torchButton=button("",()->{if(camera!=null&&camera.getCameraInfo().hasFlashUnit()){torch=!torch;camera.getCameraControl().enableTorch(torch);refreshLabels();}else message("No torch on this lens");});cell(second,torchButton);controls.addView(second);
        LinearLayout zoomRow=row();zoomLabel=text(label("zoom")+" 1.0×",12,ACCENT);zoomRow.addView(zoomLabel,new LinearLayout.LayoutParams(dp(100),-2));
        zoomSlider=new SeekBar(this);zoomSlider.setMax(100);zoomSlider.setContentDescription(label("zoom"));zoomSlider.setProgressTintList(android.content.res.ColorStateList.valueOf(ACCENT));zoomSlider.setThumbTintList(android.content.res.ColorStateList.valueOf(ACCENT));zoomRow.addView(zoomSlider,new LinearLayout.LayoutParams(0,dp(40),1));controls.addView(zoomRow);
        zoomSlider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){}public void onStopTrackingTouch(SeekBar b){}public void onProgressChanged(SeekBar b,int n,boolean user){if(user&&camera!=null)camera.getCameraControl().setLinearZoom(n/100f);}});
        LinearLayout exposureRow=row();exposureLabel=text(label("exposure")+" +0.0",12,ACCENT);exposureRow.addView(exposureLabel,new LinearLayout.LayoutParams(dp(100),-2));
        exposureSlider=new SeekBar(this);exposureSlider.setContentDescription("Exposure compensation");exposureSlider.setProgressTintList(android.content.res.ColorStateList.valueOf(ACCENT));exposureSlider.setThumbTintList(android.content.res.ColorStateList.valueOf(ACCENT));exposureRow.addView(exposureSlider,new LinearLayout.LayoutParams(0,dp(32),1));controls.addView(exposureRow);
        exposureSlider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){}public void onStopTrackingTouch(SeekBar b){}public void onProgressChanged(SeekBar b,int n,boolean user){if(camera!=null){ExposureState s=camera.getCameraInfo().getExposureState();int index=n+s.getExposureCompensationRange().getLower();exposureLabel.setText(label("exposure")+String.format(Locale.US," %+.1f",index*s.getExposureCompensationStep().doubleValue()));if(user)camera.getCameraControl().setExposureCompensationIndex(index);}}});
        LinearLayout capture=row();
        lensButton=button(label("flip"),()->{lens=lens.equals("back")?"front":"back";initialZoom=1;initialExposure=0;bind();});cell(capture,lensButton);
        shutter=button("",()->shutter());shutter.setTextColor(ON_ACCENT);android.graphics.drawable.GradientDrawable bg=new android.graphics.drawable.GradientDrawable();bg.setColor(ACCENT);bg.setCornerRadius(dp(buttonRadius));shutter.setBackground(bg);cell(capture,shutter);
        pause=button("",()->{if(recording==null)return;if(paused)recording.resume();else recording.pause();paused=!paused;refreshLabels();});cell(capture,pause);controls.addView(capture);
        LinearLayout modes=row();modeButton=button("",()->{mode=mode.equals("photo")?"video":"photo";bind();});cell(modes,modeButton);
        audioButton=button("",()->{if(recording!=null)return;audio=!audio;refreshLabels();});cell(modes,audioButton);controls.addView(modes);
        controlViews.put("flash",flashButton);controlViews.put("timer",timerButton);controlViews.put("grid",gridButton);controlViews.put("quality",qualityButton);controlViews.put("ratio",ratioButton);controlViews.put("torch",torchButton);controlViews.put("zoom",zoomRow);controlViews.put("exposure",exposureRow);controlViews.put("flip",lensButton);controlViews.put("shutter",shutter);controlViews.put("pause",pause);controlViews.put("mode",modeButton);controlViews.put("audio",audioButton);
        controlsScroll=new ScrollView(this){@Override protected void onMeasure(int w,int h){boolean side=controlsPosition.equals("auto")&&getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE;if(!side&&MeasureSpec.getMode(h)!=MeasureSpec.UNSPECIFIED)h=MeasureSpec.makeMeasureSpec(Math.max(dp(48),MeasureSpec.getSize(h)-dp(100)),MeasureSpec.AT_MOST);super.onMeasure(w,h);}};controlsScroll.setFillViewport(false);controlsScroll.addView(controls);layoutBody();renderControls();
        ScaleGestureDetector pinch=new ScaleGestureDetector(this,new ScaleGestureDetector.SimpleOnScaleGestureListener(){@Override public boolean onScale(ScaleGestureDetector detector){if(camera!=null){ZoomState z=camera.getCameraInfo().getZoomState().getValue();if(z!=null)camera.getCameraControl().setZoomRatio(Math.max(z.getMinZoomRatio(),Math.min(z.getMaxZoomRatio(),z.getZoomRatio()*detector.getScaleFactor())));}return true;}});
        view.setOnTouchListener((v,e)->{pinch.onTouchEvent(e);if(e.getAction()==MotionEvent.ACTION_UP&&!pinch.isInProgress()&&e.getPointerCount()==1&&camera!=null){if(focusDistance>=0){focusDistance=-1;applyManual(false);}MeteringPoint p=view.getMeteringPointFactory().createPoint(e.getX(),e.getY());camera.getCameraControl().startFocusAndMetering(new FocusMeteringAction.Builder(p).setAutoCancelDuration(3,TimeUnit.SECONDS).build());overlay.fx=e.getX();overlay.fy=e.getY();overlay.invalidate();main.postDelayed(()->{overlay.fx=-1;overlay.invalidate();},1500);}return true;});
        setContentView(root);
    }
    private void refreshLabels(){
        flashButton.setText(label("flash")+" "+flash);timerButton.setText(label("timer")+" "+timer+"s");gridButton.setText(label("grid")+" "+(grid?"on":"off"));qualityButton.setText(label("quality")+" "+quality);ratioButton.setText(label("ratio")+" "+ratio);torchButton.setText(label("torch")+" "+(torch?"on":"off"));audioButton.setText(label("audio")+" "+(audio?"on":"off"));modeButton.setText(label("mode")+" "+mode);
        shutter.setText(label(recording!=null?"stop":mode.equals("photo")?"capture":"record"));pause.setText(label(paused?"resume":"pause"));
        for(View v:controlViews.values())if(v instanceof TextView)v.setContentDescription(((TextView)v).getText());
    }
    private void renderControls(){
        for(View v:controlViews.values())if(v.getParent() instanceof ViewGroup)((ViewGroup)v.getParent()).removeView(v);
        controls.removeAllViews();controls.addView(status);refreshLabels();LinearLayout current=null;int count=0;
        for(String key:controlOrder){View v=controlViews.get(key);if(v==null||key.equals("pause")&&!mode.equals("video"))continue;
            if(key.equals("zoom")||key.equals("exposure")){current=null;count=0;controls.addView(v,new LinearLayout.LayoutParams(-1,-2));}
            else {if(current==null||count==3){current=row();controls.addView(current);count=0;}cell(current,v);count++;}
        }
    }
    private void layoutBody(){
        boolean wide=controlsPosition.equals("auto")&&getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE;
        body.removeAllViews();body.setOrientation(wide?LinearLayout.HORIZONTAL:LinearLayout.VERTICAL);
        if(controlsPosition.equals("top"))body.addView(controlsScroll);
        body.addView(stage);if(!controlsPosition.equals("top"))body.addView(controlsScroll);
        stage.setLayoutParams(new LinearLayout.LayoutParams(wide?0:-1,wide?-1:0,1));
        controlsScroll.setLayoutParams(new LinearLayout.LayoutParams(wide?dp(300):-1,wide?-1:-2));
    }
    @Override public void onConfigurationChanged(@NonNull Configuration c){
        super.onConfigurationChanged(c);layoutBody();
        int rotation=getWindowManager().getDefaultDisplay().getRotation();
        if(preview!=null)preview.setTargetRotation(rotation);
        if(photo!=null)photo.setTargetRotation(rotation);
        if(video!=null)video.setTargetRotation(rotation);
    }
    private void message(String s){if(status!=null)status.setText(s);}
    private interface Selection{void set(String value);}
    private void choose(String title,String[] values,Selection cb){if(busy||recording!=null||countdown)return;new androidx.appcompat.app.AlertDialog.Builder(this).setTitle(title).setItems(values,(d,n)->cb.set(values[n])).setNegativeButton("Cancel",null).show();}
    private void details(){String s=capabilities(this);try{s=new JSONObject(s).toString(2);}catch(Exception ignored){}new androidx.appcompat.app.AlertDialog.Builder(this).setTitle("Device capabilities").setMessage(s+"\n\nRAW capture and vendor night/portrait modes are not enabled by this API.").setPositiveButton("OK",null).show();}
    private void pro(){if(recording!=null||busy||countdown||review!=null)return;new androidx.appcompat.app.AlertDialog.Builder(this).setTitle("Pro controls").setItems(new String[]{"Auto exposure","ISO 100 · 1/100 s","ISO 200 · 1/100 s","ISO 400 · 1/200 s","ISO 800 · 1/100 s","White balance","Focus distance","Device capabilities"},(d,n)->{
        if(n==7){details();return;}if(n==5){choose("White balance",new String[]{"auto","daylight","cloudy","incandescent","fluorescent"},v->changeManual(manualIso,shutterMs,focusDistance,v));return;}
        if(n==6){choose("Focus distance (diopters)",new String[]{"Auto","Infinity","2","5"},v->changeManual(manualIso,shutterMs,v.equals("Auto")?-1:v.equals("Infinity")?0:Float.parseFloat(v),whiteBalance));return;}
        int[] iso={0,100,200,400,800};double[] ms={0,10,10,5,10};changeManual(iso[n],ms[n],focusDistance,whiteBalance);
    }).setNegativeButton("Close",null).show();}
    private void changeManual(int iso,double ms,float focus,String wb){int oldIso=manualIso;double oldMs=shutterMs;float oldFocus=focusDistance;String oldWb=whiteBalance;manualIso=iso;shutterMs=ms;focusDistance=focus;whiteBalance=wb;if(!applyManual(false)){manualIso=oldIso;shutterMs=oldMs;focusDistance=oldFocus;whiteBalance=oldWb;}}
    private int awbMode(){switch(whiteBalance){case "daylight":return CaptureRequest.CONTROL_AWB_MODE_DAYLIGHT;case "cloudy":return CaptureRequest.CONTROL_AWB_MODE_CLOUDY_DAYLIGHT;case "incandescent":return CaptureRequest.CONTROL_AWB_MODE_INCANDESCENT;case "fluorescent":return CaptureRequest.CONTROL_AWB_MODE_FLUORESCENT;default:return CaptureRequest.CONTROL_AWB_MODE_AUTO;}}
    private boolean applyManual(boolean initial){
        if(camera==null)return false;
        try{Camera2CameraInfo ci=Camera2CameraInfo.from(camera.getCameraInfo());CaptureRequestOptions.Builder b=new CaptureRequestOptions.Builder();
            if(manualIso>0){int[] caps=ci.getCameraCharacteristic(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES);boolean supported=false;if(caps!=null)for(int c:caps)supported|=c==CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR;
                android.util.Range<Integer> sensitivity=ci.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);android.util.Range<Long> times=ci.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);long ns=(long)(shutterMs*1000000);
                if(!supported||sensitivity==null||times==null||!sensitivity.contains(manualIso)||!times.contains(ns))throw new IllegalArgumentException("ISO/shutter outside this lens's supported range");
                b.setCaptureRequestOption(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);b.setCaptureRequestOption(CaptureRequest.SENSOR_SENSITIVITY,manualIso);b.setCaptureRequestOption(CaptureRequest.SENSOR_EXPOSURE_TIME,ns);
            }
            if(focusDistance>=0){Float max=ci.getCameraCharacteristic(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE);if(max==null||max<=0||focusDistance>max)throw new IllegalArgumentException("Manual focus unavailable at this distance");b.setCaptureRequestOption(CaptureRequest.CONTROL_AF_MODE,CaptureRequest.CONTROL_AF_MODE_OFF);b.setCaptureRequestOption(CaptureRequest.LENS_FOCUS_DISTANCE,focusDistance);}
            if(!whiteBalance.equals("auto")){int[] modes=ci.getCameraCharacteristic(CameraCharacteristics.CONTROL_AWB_AVAILABLE_MODES);boolean supported=false;if(modes!=null)for(int m:modes)supported|=m==awbMode();if(!supported)throw new IllegalArgumentException("White balance mode unavailable");b.setCaptureRequestOption(CaptureRequest.CONTROL_AWB_MODE,awbMode());}
            applyFlash();
            ListenableFuture<Void> request=Camera2CameraControl.from(camera.getCameraControl()).setCaptureRequestOptions(b.build());
            int g=generation, m=++manualGeneration;ready=false;shutter.setEnabled(false);
            request.addListener(()->{if(destroyed||done||g!=generation||m!=manualGeneration)return;try{request.get();ready=true;shutter.setEnabled(true);exposureSlider.setEnabled(manualIso==0&&camera.getCameraInfo().getExposureState().isExposureCompensationSupported());message(manualIso==0?lens+" · auto exposure":String.format(Locale.US,"ISO %d · %.1f ms",manualIso,shutterMs));}catch(Exception e){if(initial)finishResult(false,"","unsupported_controls");else{manualIso=0;shutterMs=0;focusDistance=-1;whiteBalance="auto";android.widget.Toast.makeText(this,"Camera rejected the controls; restored automatic mode",android.widget.Toast.LENGTH_LONG).show();bind();}}},ContextCompat.getMainExecutor(this));
            return true;
        }catch(Exception e){if(initial)finishResult(false,"","unsupported_controls: "+e.getMessage());else message(e.getMessage());return false;}
    }
    @Override public void onRequestPermissionsResult(int request,@NonNull String[] p,@NonNull int[] r){super.onRequestPermissionsResult(request,p,r);if(request==901){if(r.length>0&&r[0]==PackageManager.PERMISSION_GRANTED)startProvider();else finishResult(false,"","permission_denied");}else if(request==902){if(r.length>0&&r[0]==PackageManager.PERMISSION_GRANTED)startRecording();else{message("Microphone denied. Turn Mic off to record without audio.");shutter.setEnabled(true);}}}
    private void startProvider(){ListenableFuture<ProcessCameraProvider> f=ProcessCameraProvider.getInstance(this);f.addListener(()->{try{if(isFinishing()||destroyed)return;provider=f.get();bind();}catch(Exception e){finishResult(false,"","camera_unavailable");}},ContextCompat.getMainExecutor(this));}
    private Quality quality(){switch(quality){case "uhd":return Quality.UHD;case "hd":return Quality.HD;case "sd":return Quality.SD;default:return Quality.FHD;}}
    private void bind(){
        if(provider==null||isFinishing()||destroyed||recording!=null||busy||countdown)return;
        ready=false;int g=++generation;torch=false;int rotation=getWindowManager().getDefaultDisplay().getRotation();
        CameraSelector selector=new CameraSelector.Builder().requireLensFacing(lens.equals("front")?CameraSelector.LENS_FACING_FRONT:CameraSelector.LENS_FACING_BACK).build();
        try{
            if(!provider.hasCamera(selector)){
                lens=lens.equals("front")?"back":"front";
                selector=new CameraSelector.Builder().requireLensFacing(lens.equals("front")?CameraSelector.LENS_FACING_FRONT:CameraSelector.LENS_FACING_BACK).build();
                if(!provider.hasCamera(selector)){finishResult(false,"","camera_unavailable");return;}
                android.widget.Toast.makeText(this,"Requested lens unavailable; using "+lens,android.widget.Toast.LENGTH_SHORT).show();
            }
            provider.unbindAll();
            int aspect=ratio.equals("16:9")?AspectRatio.RATIO_16_9:AspectRatio.RATIO_4_3;
            preview=new Preview.Builder().setTargetAspectRatio(mode.equals("video")?AspectRatio.RATIO_16_9:aspect).setTargetRotation(rotation).build();preview.setSurfaceProvider(view.getSurfaceProvider());
            if(mode.equals("photo")){
                photo=new ImageCapture.Builder().setTargetAspectRatio(aspect).setJpegQuality(jpegQuality).setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY).setTargetRotation(rotation).build();
                camera=provider.bindToLifecycle(this,selector,preview,photo);video=null;
            }else{
                Recorder recorder=new Recorder.Builder().setQualitySelector(QualitySelector.from(quality(),FallbackStrategy.lowerQualityOrHigherThan(quality()))).build();
                video=new VideoCapture.Builder<>(recorder).setMirrorMode(mirror?MirrorMode.MIRROR_MODE_ON_FRONT_ONLY:MirrorMode.MIRROR_MODE_OFF).setTargetRotation(rotation).build();
                camera=provider.bindToLifecycle(this,selector,preview,video);photo=null;
            }
            applyFlash();
            camera.getCameraInfo().getZoomState().observe(this,z->{if(g!=generation||z==null)return;zoomSlider.setProgress(Math.round(z.getLinearZoom()*100));zoomLabel.setText(label("zoom")+String.format(Locale.US," %.1f×",z.getZoomRatio()));if(recording==null&&!busy&&!countdown)message(String.format(Locale.US,"%s · %.1f× · tap to focus",lens,z.getZoomRatio()));});
            ZoomState z=camera.getCameraInfo().getZoomState().getValue();if(z!=null)camera.getCameraControl().setZoomRatio(Math.max(z.getMinZoomRatio(),Math.min(z.getMaxZoomRatio(),initialZoom)));
            ExposureState es=camera.getCameraInfo().getExposureState();exposureSlider.setEnabled(es.isExposureCompensationSupported());int lo=es.getExposureCompensationRange().getLower(),hi=es.getExposureCompensationRange().getUpper();exposureSlider.setMax(hi-lo);int exp=Math.max(lo,Math.min(hi,initialExposure));exposureSlider.setProgress(exp-lo);if(es.isExposureCompensationSupported())camera.getCameraControl().setExposureCompensationIndex(exp);
            ready=true;pause.setEnabled(false);qualityButton.setEnabled(mode.equals("video"));renderControls();message(lens+" · "+mode+" · tap to focus");
        }catch(Exception e){message("Unsupported camera configuration. Try another lens or quality.");shutter.setEnabled(false);}
        if(ready){shutter.setEnabled(true);applyManual(true);}
    }
    private void applyFlash(){if(photo!=null){int f=flash.equals("on")?ImageCapture.FLASH_MODE_ON:flash.equals("auto")?ImageCapture.FLASH_MODE_AUTO:ImageCapture.FLASH_MODE_OFF;photo.setFlashMode(manualIso==0&&camera.getCameraInfo().hasFlashUnit()?f:ImageCapture.FLASH_MODE_OFF);}if(flashButton!=null)flashButton.setEnabled(manualIso==0&&mode.equals("photo")&&camera!=null&&camera.getCameraInfo().hasFlashUnit());}
    private void shutter(){if(recording!=null){recording.stop();shutter.setEnabled(false);return;}if(!ready||busy||countdown||recordingStarting)return;if(timer>0){countdown=true;tick(timer);}else performCapture();}
    private void tick(int n){if(!countdown||done)return;if(n==0){countdown=false;performCapture();return;}message("Capture in "+n);main.postDelayed(()->tick(n-1),1000);}
    private void performCapture(){if(mode.equals("photo"))takePhoto();else if(audio&&ContextCompat.checkSelfPermission(this,Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},902);}else startRecording();}
    private File output(String ext)throws Exception{File dir=new File(getFilesDir(),"apkpy_camera");if(!dir.isDirectory()&&!dir.mkdirs())throw new java.io.IOException("storage_unavailable");return File.createTempFile("capture_",ext,dir);}
    private void takePhoto(){
        if(photo==null||busy)return;busy=true;shutter.setEnabled(false);message("Saving photo…");
        try{pending=output(".jpg");ImageCapture.Metadata m=new ImageCapture.Metadata();m.setReversedHorizontal(mirror&&lens.equals("front"));ImageCapture.OutputFileOptions o=new ImageCapture.OutputFileOptions.Builder(pending).setMetadata(m).build();
            final File capturing=pending;
            photo.takePicture(o,io,new ImageCapture.OnImageSavedCallback(){public void onImageSaved(@NonNull ImageCapture.OutputFileResults r){if(destroyed){capturing.delete();return;}main.post(()->{busy=false;if(done||destroyed){discard();return;}showReview();});}public void onError(@NonNull ImageCaptureException e){if(destroyed){capturing.delete();return;}main.post(()->{busy=false;discard();if(!destroyed){shutter.setEnabled(true);message("Photo failed: "+e.getMessage());}});}});
        }catch(Exception e){busy=false;discard();shutter.setEnabled(true);message("Could not create the photo file");}
    }
    private void startRecording(){
        if(video==null||recording!=null||recordingStarting||done)return;
        try{pending=output(".mp4");final File recordingFile=pending;PendingRecording r=video.getOutput().prepareRecording(this,new FileOutputOptions.Builder(pending).build());if(audio)r=r.withAudioEnabled();recordingStarting=true;shutter.setEnabled(false);
            recording=r.start(ContextCompat.getMainExecutor(this),event->{
                if(destroyed){if(event instanceof VideoRecordEvent.Finalize)recordingFile.delete();return;}
                if(event instanceof VideoRecordEvent.Start){recordingStarting=false;shutter.setEnabled(true);pause.setEnabled(true);paused=false;lensButton.setEnabled(false);modeButton.setEnabled(false);refreshLabels();}
                if(event instanceof VideoRecordEvent.Status){long sec=event.getRecordingStats().getRecordedDurationNanos()/1000000000L;message(String.format(Locale.US,"%s %02d:%02d · %s",paused?"PAUSED":"REC",sec/60,sec%60,audio?"mic on":"silent"));if(sec>=maxDuration&&recording!=null)recording.stop();}
                if(event instanceof VideoRecordEvent.Finalize){VideoRecordEvent.Finalize f=(VideoRecordEvent.Finalize)event;recording=null;recordingStarting=false;pause.setEnabled(false);lensButton.setEnabled(true);modeButton.setEnabled(true);shutter.setEnabled(true);refreshLabels();if(done){discard();return;}if(f.hasError()){discard();message("Recording failed ("+f.getError()+"). Try a lower quality.");}else showReview();}
            });
        }catch(Exception e){recordingStarting=false;discard();message("Recording could not start: "+e.getMessage());shutter.setEnabled(true);}
    }
    private void showReview(){
        if(done||destroyed||pending==null||!pending.isFile())return;ready=false;if(provider!=null)provider.unbindAll();
        review=new FrameLayout(this);review.setBackgroundColor(BG);
        if(pending.getName().endsWith(".mp4")){reviewVideo=new VideoView(this);reviewVideo.setVideoPath(pending.getAbsolutePath());reviewVideo.setOnPreparedListener(mp->{mp.setLooping(true);reviewVideo.start();});review.addView(reviewVideo,new FrameLayout.LayoutParams(-1,-1));}
        else {ImageView image=new ImageView(this);image.setScaleType(ImageView.ScaleType.FIT_CENTER);review.addView(image,new FrameLayout.LayoutParams(-1,-1));final File f=pending;io.execute(()->{Bitmap bitmap=reviewBitmap(f);main.post(()->{if(!done&&!destroyed&&review!=null)image.setImageBitmap(bitmap);});});}
        LinearLayout bar=row();bar.setBackgroundColor(BG);cell(bar,button(label("retake"),()->{removeReview();discard();if(provider==null)startProvider();else bind();}));TextView accept=button(label(pending.getName().endsWith(".mp4")?"use_video":"use_photo"),()->{try{Uri uri=FileProvider.getUriForFile(this,getPackageName()+".fileprovider",pending);pending=null;finishResult(true,uri.toString(),"ok");}catch(Exception e){message("Could not share the captured file");}});accept.setTextColor(ON_ACCENT);android.graphics.drawable.GradientDrawable acceptBackground=new android.graphics.drawable.GradientDrawable();acceptBackground.setColor(ACCENT);acceptBackground.setCornerRadius(dp(buttonRadius));accept.setBackground(acceptBackground);cell(bar,accept);
        FrameLayout.LayoutParams bp=new FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM);review.addView(bar,bp);stage.addView(review,new FrameLayout.LayoutParams(-1,-1));controlsScroll.setVisibility(View.GONE);
    }
    private void removeReview(){if(reviewVideo!=null){reviewVideo.stopPlayback();reviewVideo=null;}if(review!=null){stage.removeView(review);review=null;}controlsScroll.setVisibility(View.VISIBLE);}
    private Intent answer(String path,String reason){return new Intent().putExtra("resultCallback",resultTag).putExtra("errorCallback",errorTag).putExtra("path",path).putExtra("reason",reason);}
    private void finishResult(boolean ok,String path,String reason){if(done)return;done=true;countdown=false;setResult(ok?RESULT_OK:RESULT_CANCELED,answer(path,reason));finish();}
    private void cancel(){countdown=false;if(recording!=null){done=true;recording.stop();setResult(RESULT_CANCELED,answer("","cancelled"));finish();}else{discard();finishResult(false,"","cancelled");}}
    private void discard(){if(pending!=null){pending.delete();pending=null;}}
    @Override protected void onPause(){super.onPause();countdown=false;if(recording!=null)recording.stop();if(camera!=null)camera.getCameraControl().enableTorch(false);torch=false;}
    @Override protected void onSaveInstanceState(@NonNull Bundle b){
        if(pending!=null&&review!=null)b.putString("pending",pending.getAbsolutePath());
        ZoomState z=camera==null?null:camera.getCameraInfo().getZoomState().getValue();
        b.putBundle("cameraOptions",options("mode",mode,"lens",lens,"flash",flash,"quality",quality,"aspect_ratio",ratio,"grid",""+grid,"audio",""+audio,"mirror",""+mirror,"timer",""+timer,"max_duration",""+maxDuration,"jpeg_quality",""+jpegQuality,"zoom",""+(z==null?initialZoom:z.getZoomRatio()),"exposure",""+(camera==null?initialExposure:camera.getCameraInfo().getExposureState().getExposureCompensationIndex()),"iso",""+manualIso,"shutter_ms",""+shutterMs,"focus_distance",""+focusDistance,"white_balance",whiteBalance));
        super.onSaveInstanceState(b);
    }
    @Override protected void onDestroy(){destroyed=true;generation++;main.removeCallbacksAndMessages(null);if(recording!=null)recording.close();if(provider!=null)provider.unbindAll();if(reviewVideo!=null)reviewVideo.stopPlayback();io.shutdown();if(isFinishing()&&!busy)discard();super.onDestroy();}

    private final class Overlay extends android.view.View {
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);float fx=-1,fy;
        Overlay(){super(ApkpyCameraActivity.this);setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);}
        @Override protected void onDraw(Canvas c){paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(1));paint.setColor(0x55FFFFFF);if(grid){for(int n=1;n<3;n++){c.drawLine(getWidth()*n/3f,0,getWidth()*n/3f,getHeight(),paint);c.drawLine(0,getHeight()*n/3f,getWidth(),getHeight()*n/3f,paint);}}if(fx>=0){paint.setColor(ACCENT);c.drawRoundRect(fx-dp(25),fy-dp(25),fx+dp(25),fy+dp(25),dp(8),dp(8),paint);}}
    }
    private Bitmap reviewBitmap(File f){
        try{BitmapFactory.Options o=new BitmapFactory.Options();o.inJustDecodeBounds=true;BitmapFactory.decodeFile(f.getPath(),o);int sample=1;while(Math.max(o.outWidth,o.outHeight)/sample>1800)sample*=2;o.inSampleSize=sample;o.inJustDecodeBounds=false;Bitmap bitmap=BitmapFactory.decodeFile(f.getPath(),o);if(bitmap==null)return null;
            androidx.exifinterface.media.ExifInterface exif=new androidx.exifinterface.media.ExifInterface(f);Matrix matrix=new Matrix();if(exif.isFlipped())matrix.postScale(-1,1);matrix.postRotate(exif.getRotationDegrees());return Bitmap.createBitmap(bitmap,0,0,bitmap.getWidth(),bitmap.getHeight(),matrix,true);
        }catch(Exception e){return null;}
    }
    public static String capabilities(android.content.Context context){
        JSONObject out=new JSONObject();JSONArray cameras=new JSONArray();
        try{
            CameraManager m=(CameraManager)context.getSystemService(CAMERA_SERVICE);
            for(String id:m.getCameraIdList()){
                CameraCharacteristics c=m.getCameraCharacteristics(id);JSONObject item=new JSONObject();item.put("id",id);
                Integer face=c.get(CameraCharacteristics.LENS_FACING);item.put("lens",face!=null&&face==CameraCharacteristics.LENS_FACING_FRONT?"front":face!=null&&face==CameraCharacteristics.LENS_FACING_BACK?"back":"external");
                item.put("flash",Boolean.TRUE.equals(c.get(CameraCharacteristics.FLASH_INFO_AVAILABLE)));item.put("max_zoom",c.get(CameraCharacteristics.SCALER_AVAILABLE_MAX_DIGITAL_ZOOM));
                android.util.Range<Integer> ev=c.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE);if(ev!=null){item.put("min_exposure",ev.getLower());item.put("max_exposure",ev.getUpper());}
                android.util.Rational step=c.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP);item.put("exposure_step",step==null?0:step.doubleValue());
                int[] raw=c.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES);boolean manual=false,rawSupport=false;if(raw!=null)for(int cap:raw){manual|=cap==CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_MANUAL_SENSOR;rawSupport|=cap==CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW;}
                item.put("hardware_manual_sensor",manual);item.put("hardware_raw",rawSupport);
                android.util.Range<Integer> iso=c.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);if(iso!=null){item.put("min_iso",iso.getLower());item.put("max_iso",iso.getUpper());}
                android.util.Range<Long> times=c.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);if(times!=null){item.put("min_shutter_ms",times.getLower()/1000000.0);item.put("max_shutter_ms",times.getUpper()/1000000.0);}
                Float focus=c.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE);item.put("max_focus_distance",focus==null?0:focus);
                JSONArray wb=new JSONArray();int[] modes=c.get(CameraCharacteristics.CONTROL_AWB_AVAILABLE_MODES);if(modes!=null)for(int wbMode:modes){switch(wbMode){case CaptureRequest.CONTROL_AWB_MODE_AUTO:wb.put("auto");break;case CaptureRequest.CONTROL_AWB_MODE_DAYLIGHT:wb.put("daylight");break;case CaptureRequest.CONTROL_AWB_MODE_CLOUDY_DAYLIGHT:wb.put("cloudy");break;case CaptureRequest.CONTROL_AWB_MODE_INCANDESCENT:wb.put("incandescent");break;case CaptureRequest.CONTROL_AWB_MODE_FLUORESCENT:wb.put("fluorescent");break;}}item.put("white_balance_modes",wb);cameras.put(item);
            }
            out.put("simulated",false);out.put("available",cameras.length()>0);out.put("cameras",cameras);out.put("manual_controls_enabled",true);out.put("raw_capture_enabled",false);
        }catch(Exception e){try{out.put("error",e.getClass().getSimpleName());}catch(Exception ignored){}}
        return out.toString();
    }
}
